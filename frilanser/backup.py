"""حفظِ نشانه‌گذاری‌های کاربر (پیشنهاد دادم / گرفتم / نگرفتم / مبلغ) در برابر
به‌روزرسانی و تغییرِ پوشه‌ی داده‌ها.

چرا این ماژول لازم است؟
-----------------------
داده‌ها به‌طور پیش‌فرض داخلِ پوشه‌ی برنامه (`data/`) نوشته می‌شوند. اما:

* در **ویندوز** پوشه‌ی برنامه همان پوشه‌ی نصب است (`%LOCALAPPDATA%\\Frilanser`)؛
  نصبِ نسخه‌ی جدید آن را بازنویسی می‌کند و `data/projects.json` از بین می‌رود.
* در **اندروید** پوشه‌ی داده با توجه به دسترسیِ حافظه انتخاب می‌شود (ابتدا
  حافظه‌ی خارجی، بعد داخلی). اگر دسترسی بین دو اجرا عوض شود، پوشه عوض می‌شود و
  داده‌ها «ناپدید» به نظر می‌رسند — در حالی که هنوز در پوشه‌ی قبلی هستند.

راه‌حل: یک **دفترچه‌ی وضعیت** (state ledger) جداگانه که فقط فیلدهایی را که
**خود کاربر** تنظیم کرده نگه می‌دارد، در چند پوشه‌ی پایدار (بیرون از پوشه‌ی
نصب) نوشته می‌شود و هنگامِ بالا آمدن برنامه از **همه‌ی** پوشه‌های شناخته‌شده
خوانده و روی پروژه‌ها اعمال می‌شود. علاوه بر آن، از کلِ پایگاه داده نسخه‌ی
پشتیبانِ گردشی (rolling backup) گرفته می‌شود.

هیچ‌چیز به‌طور خودکار پاک نمی‌شود و هیچ‌کدام از انتخاب‌های کاربر (مثل
«گرفتم»/«نگرفتم») هرگز با مقدارِ پیش‌فرض جایگزین نمی‌شود.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable

STATE_FILE = "frilanser_state.json"
BACKUP_DIR = "backups"
MAX_BACKUPS = 12
SNAPSHOT_MIN_INTERVAL = 600  # ثانیه

#: فیلدهایی که **فقط کاربر** آن‌ها را تعیین می‌کند و باید همیشه حفظ شوند.
USER_FIELDS: tuple[str, ...] = (
    "proposal_state",
    "proposal_state_at",
    "submitted_price",
    "user_decision",
    "missed_scans",
    "history",
    "notes",
)


def _try(fn, default=None):
    try:
        return fn()
    except Exception:  # noqa: BLE001 - پوشه‌ها ممکن است در دسترس نباشند
        return default


# --------------------------------------------------------------------------- #
# انتخابِ پوشه‌های پایدار
# --------------------------------------------------------------------------- #
def _is_android() -> bool:
    return "ANDROID_ARGUMENT" in os.environ or "ANDROID_APP_PATH" in os.environ \
        or os.environ.get("ANDROID_STORAGE") is not None


def stable_dirs() -> list[Path]:
    """پوشه‌هایی که در به‌روزرسانیِ برنامه پاک نمی‌شوند (ترتیب = اولویت)."""
    dirs: list[Path] = []

    def add(p) -> None:
        if not p:
            return
        path = Path(p)
        if path not in dirs:
            dirs.append(path)

    # ۱) مسیرِ صریحِ کاربر
    forced = os.environ.get("FRILANSER_HOME")
    if forced:
        add(os.path.join(forced, "state"))

    if _is_android():
        try:
            from android.storage import (  # type: ignore  # noqa: PLC0415
                app_storage_path,
                primary_external_storage_path,
            )
            ext = _try(primary_external_storage_path)
            if ext:
                add(os.path.join(str(ext), "frilanser", "state"))
            internal = _try(app_storage_path)
            if internal:
                add(os.path.join(str(internal), "frilanser", "state"))
        except Exception:  # noqa: BLE001
            pass
        app_path = os.environ.get("ANDROID_APP_PATH") or os.environ.get("ANDROID_ARGUMENT")
        if app_path:
            add(os.path.join(os.path.dirname(str(app_path)), "frilanser", "state"))
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        local = os.environ.get("LOCALAPPDATA")
        if appdata:
            add(os.path.join(appdata, "Frilanser", "state"))
        if local:
            add(os.path.join(local, "FrilanserData", "state"))
        add(os.path.join(os.path.expanduser("~"), "frilanser", "state"))
    else:
        add(os.path.join(os.path.expanduser("~"), ".frilanser", "state"))

    return dirs


def legacy_dirs(data_dir: Path) -> list[Path]:
    """همه‌ی پوشه‌هایی که ممکن است داده‌ی قدیمی در آن‌ها مانده باشد."""
    out: list[Path] = [Path(data_dir)]
    out.extend(stable_dirs())

    # پوشه‌ی نصب (ویندوز/اجرایی): جایی که احتمالاً داده‌ی قدیمی بوده
    if getattr(sys, "frozen", False):
        try:
            exe_dir = Path(sys.executable).resolve().parent
            out.append(exe_dir / "data")
            out.append(exe_dir / "state")
        except Exception:  # noqa: BLE001
            pass
    # پوشه‌ی جاری و پوشه‌ی بسته
    out.append(Path.cwd() / "data")
    try:
        bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        out.append(bundle / "data")
    except Exception:  # noqa: BLE001
        pass
    if _is_android():
        app_path = os.environ.get("ANDROID_APP_PATH") or os.environ.get("ANDROID_ARGUMENT")
        if app_path:
            out.append(Path(os.path.dirname(str(app_path))) / "frilanser" / "data")
        for base in ("/sdcard", "/storage/emulated/0"):
            out.append(Path(base) / "frilanser" / "data")
            out.append(Path(base) / "frilanser" / "state")

    # حذفِ تکراری‌ها و موارد نامعتبر
    seen: list[Path] = []
    for p in out:
        try:
            rp = p.resolve()
        except Exception:  # noqa: BLE001
            continue
        if rp not in seen:
            seen.append(rp)
    return seen


def writable_dirs(data_dir: Path) -> list[Path]:
    """پوشه‌هایی که می‌توان در آن‌ها نوشت (برای ذخیره‌ی دفترچه)."""
    out: list[Path] = [Path(data_dir)]
    for d in stable_dirs():
        if _try(lambda d=d: (d.mkdir(parents=True, exist_ok=True), os.access(str(d), os.W_OK))[1]):
            out.append(d)
    return out


# --------------------------------------------------------------------------- #
# گرفتن و اعمال کردنِ وضعیت
# --------------------------------------------------------------------------- #
def _is_set(value) -> bool:
    if value in (None, "", [], {}, 0):
        return False
    return True


def capture(store) -> dict:
    """فیلدهای تنظیم‌شده توسط کاربر را از همه‌ی پروژه‌ها برمی‌دارد."""
    out: dict[str, dict] = {}
    for pid, p in store.projects.items():
        rec: dict = {}
        for f in USER_FIELDS:
            v = getattr(p, f, None)
            if _is_set(v):
                rec[f] = v
        if rec:
            rec["_title"] = (p.title or "")[:120]
            rec["_at"] = p.proposal_state_at or ""
            out[pid] = rec
    return out


def _record_newer(a: dict, b: dict) -> dict:
    """از دو رکورد، آن را برمی‌گرداند که داده‌ی بیشتر/جدیدتر دارد."""
    def score(r: dict) -> tuple:
        filled = sum(1 for k in USER_FIELDS if _is_set(r.get(k)))
        return (filled, str(r.get("_at") or ""))
    return a if score(a) >= score(b) else b


def load_state(paths: Iterable[Path]) -> tuple[dict, list[str]]:
    """دفترچه را از چند مسیر می‌خواند و ادغام می‌کند (جدیدتر برنده است)."""
    merged: dict[str, dict] = {}
    sources: list[str] = []
    for base in paths:
        f = Path(base) / STATE_FILE
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        projects = data.get("projects") if isinstance(data.get("projects"), dict) else data
        got = 0
        for pid, rec in projects.items():
            if not isinstance(rec, dict):
                continue
            if pid in merged:
                merged[pid] = _record_newer(merged[pid], rec)
            else:
                merged[pid] = rec
            got += 1
        if got:
            sources.append(f"{f} ({got} مورد)")
    return merged, sources


def apply_state(store, ledger: dict) -> list[str]:
    """دفترچه را روی پروژه‌های موجود اعمال می‌کند. خروجی: گزارشِ تغییرات."""
    report: list[str] = []
    for pid, rec in ledger.items():
        p = store.get(pid)
        if p is None:
            continue
        changed = []
        for f in USER_FIELDS:
            v = rec.get(f)
            if not _is_set(v):
                continue
            cur = getattr(p, f, None)
            # هرگز مقدارِ موجود را با مقدارِ خالی/کمتر جایگزین نمی‌کنیم
            if f == "history" and isinstance(v, list) and isinstance(cur, list):
                merged = list(cur)
                for item in v:
                    if item not in merged:
                        merged.append(item)
                if len(merged) != len(cur):
                    setattr(p, f, merged)
                    changed.append(f)
                continue
            if f == "notes" and isinstance(v, list) and isinstance(cur, list):
                merged = list(cur)
                for item in v:
                    if item not in merged:
                        merged.append(item)
                if len(merged) != len(cur):
                    setattr(p, f, merged)
                    changed.append(f)
                continue
            if cur != v and not (f == "missed_scans" and _is_set(cur) and cur > v):
                setattr(p, f, v)
                changed.append(f)
        if changed:
            report.append(f"{p.title[:60]} ← {', '.join(changed)}")
    if report:
        store.save()
    return report


def save_state(data_dir: Path, ledger: dict) -> list[str]:
    """دفترچه را در پوشه‌ی داده‌ها و همه‌ی پوشه‌های پایدار می‌نویسد."""
    if not ledger:
        return []
    payload = {"version": 1, "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "projects": ledger}
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    written: list[str] = []
    for d in writable_dirs(data_dir):
        try:
            d.mkdir(parents=True, exist_ok=True)
            target = Path(d) / STATE_FILE
            tmp = target.with_suffix(".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(target)
            written.append(str(target))
        except Exception:  # noqa: BLE001
            continue
    return written


def sync(store) -> list[str]:
    """دو خطِ ساده: از پروژه‌ها بگیر و در همه‌جا بنویس. (بعد از هر تغییر صدا زده می‌شود)"""
    return save_state(Path(store.dir), capture(store))


# --------------------------------------------------------------------------- #
# نسخه‌ی پشتیبانِ گردشی از کلِ پایگاه داده
# --------------------------------------------------------------------------- #
def backup_path(data_dir: Path) -> Path:
    return Path(data_dir) / BACKUP_DIR


def snapshot(store, force: bool = False) -> Path | None:
    """یک کپی زمان‌دار از projects.json می‌گیرد (حداکثر هر ۱۰ دقیقه یک‌بار)."""
    src = Path(store.dir) / "projects.json"
    if not src.exists():
        return None
    out = backup_path(Path(store.dir))
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    if not force:
        recent = sorted(out.glob("projects-*.json"), key=lambda p: p.stat().st_mtime,
                        reverse=True)
        if recent and (time.time() - recent[0].stat().st_mtime) < SNAPSHOT_MIN_INTERVAL:
            return None
    target = out / time.strftime("projects-%Y%m%d-%H%M%S.json")
    try:
        shutil.copy2(src, target)
    except OSError:
        return None
    _prune(out)
    return target


def _prune(out: Path) -> None:
    files = sorted(out.glob("projects-*.json"), key=lambda p: p.stat().st_mtime,
                   reverse=True)
    for old in files[MAX_BACKUPS:]:
        try:
            old.unlink()
        except OSError:
            pass


def list_backups(data_dir: Path) -> list[dict]:
    out = backup_path(Path(data_dir))
    if not out.exists():
        return []
    items = []
    for f in sorted(out.glob("projects-*.json"), key=lambda p: p.stat().st_mtime,
                    reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            marked = sum(1 for v in data.values()
                         if isinstance(v, dict) and v.get("proposal_state"))
            items.append({"name": f.name, "size": f.stat().st_size,
                          "count": len(data), "marked": marked,
                          "mtime": time.strftime("%Y-%m-%d %H:%M",
                                                 time.localtime(f.stat().st_mtime))})
        except Exception:  # noqa: BLE001
            continue
    return items


# --------------------------------------------------------------------------- #
# بازیابیِ کامل هنگامِ بالا آمدن برنامه
# --------------------------------------------------------------------------- #
def restore(store) -> dict:
    """دفترچه را از همه‌ی پوشه‌های شناخته‌شده می‌خواند و روی پروژه‌ها اعمال می‌کند.

    همچنین اگر پایگاه داده خالی است اما نسخه‌ی پشتیبانی وجود دارد که پروژه‌ی
    نشانه‌گذاری‌شده دارد، آن را بازمی‌گرداند.
    """
    data_dir = Path(store.dir)
    ledger, sources = load_state(legacy_dirs(data_dir))
    applied = apply_state(store, ledger) if ledger else []

    restored_from_backup = None
    if not store.projects:
        # پایگاه داده خالی است → از آخرین نسخه‌ی پشتیبان برمی‌گردانیم
        for f in sorted(backup_path(data_dir).glob("projects-*.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict) or not data:
                continue
            for pid, rec in data.items():
                if not isinstance(rec, dict):
                    continue
                try:
                    from .models import Project  # noqa: PLC0415
                    store._projects[pid] = Project.from_dict(rec)  # noqa: SLF001
                except Exception:  # noqa: BLE001
                    continue
            if store.projects:
                store.save()
                restored_from_backup = f.name
                break

    return {
        "sources": sources,
        "ledger_count": len(ledger),
        "applied": applied,
        "restored_from_backup": restored_from_backup,
        "data_dir": str(data_dir),
        "writable": [str(d) for d in writable_dirs(data_dir)],
    }


# --------------------------------------------------------------------------- #
# خروجی/ورودیِ دستی (برای کاربر)
# --------------------------------------------------------------------------- #
def export_payload(store) -> dict:
    """یک فایلِ قابلِ‌حمل از نشانه‌گذاری‌ها (برای نگه داشتن یا جابه‌جایی)."""
    return {
        "kind": "frilanser-state",
        "version": 1,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "projects": capture(store),
    }


def import_payload(store, payload: dict) -> list[str]:
    """نشانه‌گذاری‌ها را از یک فایلِ خروجی گرفته‌شده برمی‌گرداند."""
    projects = payload.get("projects") if isinstance(payload, dict) else None
    if not isinstance(projects, dict):
        raise ValueError("فایل معتبر نیست (بخش projects پیدا نشد)")
    return apply_state(store, projects)
