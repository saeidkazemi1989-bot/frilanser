"""ساخت/به‌روزرسانیِ «مانیفست نسخه» که برنامه برای به‌روزرسانی خودکار می‌خواند.

هر workflow پس از ساخت خروجی خودش این اسکریپت را صدا می‌زند؛ مانیفست به‌صورت
تجمیعی است (هر بار فقط بخش مربوط به خودش را به‌روزرسانی می‌کند):

    python scripts/make_manifest.py set apk   dist/frilanser.apk            --version 1.0.0
    python scripts/make_manifest.py set windows dist/Frilanser-Setup.exe    --version 1.0.0
    python scripts/make_manifest.py show

خروجی: dist/updates/manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "dist" / "updates" / "manifest.json"

REPO = os.environ.get("GITHUB_REPOSITORY", "saeidkazemi1989-bot/frilanser")
BRANCH = os.environ.get("GITHUB_REF_NAME", "arena/01a0e651-frilanser")
RELEASE_TAG = os.environ.get("RELEASE_TAG", "latest")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def file_url(filename: str) -> str:
    """آدرس دانلود مستقیم از فایل‌های موجود در شاخه (بدون نیاز به API)."""
    return (f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"
            f"dist/updates/{filename}")


def release_url(filename: str) -> str:
    return f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}/{filename}"


CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def _strip_conflict_markers(text: str) -> str:
    """نشانه‌های تداخلِ گیت را بیرون می‌کشد (اگر مانیفست خراب کامیت شده باشد)."""
    if not any(marker in text for marker in CONFLICT_MARKERS):
        return text
    keep: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<<<<<<<") or stripped.startswith(">>>>>>>"):
            continue
        if stripped == "=======":
            continue
        keep.append(line)
    return "\n".join(keep)


def load() -> dict:
    """مانیفست را می‌خواند؛ اگر خراب یا آمیخته به نشانه‌ی تداخل بود، ترمیم می‌کند."""
    empty = {"version": "", "generated_at": "", "release_url": "", "notes": [],
             "assets": {}}
    if not MANIFEST.exists():
        return empty
    raw = MANIFEST.read_text(encoding="utf-8", errors="replace")
    for candidate in (raw, _strip_conflict_markers(raw)):
        try:
            data = json.loads(candidate)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(data, dict):
            data.setdefault("assets", {})
            data.setdefault("notes", [])
            return data
    # آخرین تلاش: هر ورودیِ سالمِ «version» را از متن بیرون می‌کشیم
    for line in raw.splitlines():
        if '"version"' in line:
            try:
                empty["version"] = json.loads("{" + line.strip().rstrip(",") + "}")["version"]
                break
            except Exception:  # noqa: BLE001
                continue
    print("! مانیفستِ قبلی خراب بود و از نو ساخته می‌شود", file=sys.stderr)
    return empty


def save(data: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")


def cmd_set(args) -> int:
    src = Path(args.file)
    if not src.exists():
        print(f"! فایل پیدا نشد: {src}", file=sys.stderr)
        return 1

    data = load()
    data["version"] = args.version
    data["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data["release_url"] = f"https://github.com/{REPO}/releases/tag/{RELEASE_TAG}"
    if args.notes:
        data["notes"] = [n.strip() for n in args.notes.splitlines() if n.strip()]
    elif not data.get("notes"):
        data["notes"] = []

    # فایل را کنار مانیفست هم می‌گذاریم تا آدرسِ raw ثابت و همیشه در دسترس باشد
    target_dir = MANIFEST.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / src.name
    if src.resolve() != target.resolve():
        target.write_bytes(src.read_bytes())

    data.setdefault("assets", {})[args.key] = {
        "file": src.name,
        "size": src.stat().st_size,
        "sha256": sha256_of(src),
        "url": release_url(src.name),
        "mirror": file_url(src.name),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save(data)
    print(f"✓ مانیفست به‌روزرسانی شد: {args.key} → {src.name} "
          f"({src.stat().st_size:,} بایت)")
    return 0


def cmd_show(args) -> int:
    data = load()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_verify(args) -> int:
    """بررسیِ سلامتِ مانیفست؛ اگر JSON سالم نباشد با کدِ خطا خارج می‌شود."""
    if not MANIFEST.exists():
        print(f"! مانیفست وجود ندارد: {MANIFEST}", file=sys.stderr)
        return 1
    raw = MANIFEST.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"! مانیفست JSON سالمی نیست: {exc}", file=sys.stderr)
        return 1
    if any(marker in raw for marker in CONFLICT_MARKERS):
        print("! مانیفست هنوز نشانه‌ی تداخل (conflict) دارد", file=sys.stderr)
        return 1
    if not isinstance(data, dict) or not str(data.get("version") or "").strip():
        print("! مانیفست نسخه (version) ندارد", file=sys.stderr)
        return 1
    print(f"✓ مانیفست سالم است: نسخه {data['version']} | "
          f"دارایی‌ها: {', '.join(sorted((data.get('assets') or {})))}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ساخت مانیفست به‌روزرسانی")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("set", help="ثبت یک خروجی در مانیفست")
    p.add_argument("key", choices=["android", "windows", "linux"])
    p.add_argument("file")
    p.add_argument("--version", required=True)
    p.add_argument("--notes", default="")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("show", help="نمایش مانیفست")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("verify", help="بررسیِ سلامتِ مانیفست (برای CI)")
    p.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
