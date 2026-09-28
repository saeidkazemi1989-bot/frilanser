"""به‌روزرسانیِ درون‌برنامه‌ای (بدون نیاز به مراجعه‌ی دستی به گیت‌هاب).

نکته: منبع پیش‌فرض، مانیفستِ `dist/updates/manifest.json` روی شاخه است و
در صورت نبودن آن، آخرین انتشار گیت‌هاب خوانده می‌شود.
"""

گردش کار:
    ۱) برنامه یک «مانیفست نسخه» را از اینترنت می‌خواند (JSON ساده)
    ۲) نسخه‌ی خودش را با نسخه‌ی موجود مقایسه می‌کند
    ۳) در صورت نیاز فایل نصب (APK یا EXE) را دانلود و امضای آن را بررسی می‌کند
    ۴) نصب را آغاز می‌کند: در اندروید با Intent نصب، در ویندوز با اجرای نصب‌کننده

مانیفست به‌طور خودکار توسط CI (دو workflow ساخت ویندوز و اندروید) تولید می‌شود و
در `dist/updates/manifest.json` روی شاخه قرار می‌گیرد. آدرس آن را می‌توان در
`config.toml` تغییر داد (بخش `[update]`) تا از هرMirror دلخوانی استفاده شود.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from .version import (
    DEFAULT_BRANCH,
    REPO_NAME,
    REPO_OWNER,
    __version__,
    is_newer,
    platform_key,
)

MANIFEST_REL = "dist/updates/manifest.json"
STATE_FILE = "update-status.json"
DEFAULT_MANIFEST_URL = (
    f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/"
    f"{DEFAULT_BRANCH}/dist/updates/manifest.json"
)
RELEASE_API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"


# --------------------------------------------------------------------------- #
# کمکی‌ها
# --------------------------------------------------------------------------- #
def _request():
    try:
        import requests  # وابستگی پروژه

        return requests
    except Exception:  # noqa: BLE001
        return None


def _cfg_value(cfg, key: str, default: str = "") -> str:
    try:
        return str(cfg.raw.get("update", {}).get(key, default) or default)
    except Exception:  # noqa: BLE001
        return default


def manifest_urls(cfg) -> list[str]:
    """فهرست آدرس‌هایی که برای یافتن مانیفست امتحان می‌شوند."""
    urls = [_cfg_value(cfg, "manifest_url", ""), DEFAULT_MANIFEST_URL]
    return [u for u in dict.fromkeys(u for u in urls if u)]


def state_path(cfg) -> Path:
    return Path(cfg.outbox_dir) / STATE_FILE


def read_state(cfg) -> dict:
    path = state_path(cfg)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _write_state(cfg, **fields) -> dict:
    state = read_state(cfg)
    state.update(fields)
    state["updated_at"] = time.time()
    try:
        state_path(cfg).parent.mkdir(parents=True, exist_ok=True)
        state_path(cfg).write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    except OSError:
        pass
    return state


# --------------------------------------------------------------------------- #
# بررسی نسخه
# --------------------------------------------------------------------------- #
def _from_manifest(data: dict, key: str) -> dict | None:
    latest = str(data.get("version") or "").strip()
    if not latest:
        return None
    assets = data.get("assets") or {}
    asset = assets.get(key) or {}
    return {
        "latest": latest,
        "notes": list(data.get("notes") or []),
        "asset": {
            "file": asset.get("file", ""),
            "url": asset.get("url", ""),
            "size": int(asset.get("size") or 0),
            "sha256": asset.get("sha256") or "",
        },
        "release_url": data.get("release_url", ""),
    }


def _from_release_api(data: dict, key: str) -> dict | None:
    """اگر مانیفست در دسترس نبود، از API انتشارهای گیت‌هاب استفاده می‌کنیم."""
    tag = str(data.get("tag_name") or data.get("name") or "").strip()
    version = tag.lstrip("v")
    if not version:
        return None
    wanted = (".apk",) if key == "android" else (".exe", ".msi", ".zip")
    asset, url, size = "", "", 0
    for a in data.get("assets") or []:
        name = str(a.get("name") or "")
        if name.lower().endswith(wanted):
            asset, url, size = name, a.get("browser_download_url", ""), int(a.get("size") or 0)
            if key == "android" or "Setup" in name:
                break
    return {
        "latest": version,
        "notes": (data.get("body") or "").splitlines()[:8],
        "asset": {"file": asset, "url": url, "size": size, "sha256": ""},
        "release_url": data.get("html_url", ""),
    }


def check_update(cfg, key: str | None = None, timeout: int = 15) -> dict:
    """نسخه‌ی موجود را بررسی می‌کند (بدون تغییر در برنامه)."""
    key = key or platform_key()
    requests = _request()
    result = {"ok": False, "error": "", "current": __version__, "platform": key,
              "latest": __version__, "has_update": False, "notes": [], "asset": {},
              "release_url": "", "source": ""}
    if requests is None:
        result["error"] = "کتابخانه‌ی requests در دسترس نیست"
        return result

    found: dict | None = None
    last_error = ""
    for url in manifest_urls(cfg):
        try:
            resp = requests.get(url, timeout=timeout,
                                headers={"Cache-Control": "no-cache"})
            if resp.status_code == 200:
                data = resp.json()
                found = _from_manifest(data, key)
                if found:
                    found["source"] = url
                    break
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"

    if not found:
        try:
            resp = requests.get(RELEASE_API, timeout=timeout)
            if resp.status_code == 200:
                found = _from_release_api(resp.json(), key)
                if found:
                    found["source"] = RELEASE_API
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"

    if not found:
        result["error"] = last_error or "نسخه‌ی جدیدی پیدا نشد"
        return result

    result.update({
        "ok": True,
        "latest": found["latest"],
        "has_update": is_newer(found["latest"], __version__),
        "notes": found.get("notes") or [],
        "asset": found.get("asset") or {},
        "release_url": found.get("release_url", ""),
        "source": found.get("source", ""),
    })
    _write_state(cfg, last_check=result)
    return result


# --------------------------------------------------------------------------- #
# دانلود و بررسی امضا
# --------------------------------------------------------------------------- #
def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def download(cfg, url: str, dest: Path, sha256: str = "") -> dict:
    """دانلود فایل با ذخیره‌ی وضعیت پیشرفت (برای نمایش در رابط کاربری)."""
    requests = _request()
    if requests is None:
        return {"ok": False, "error": "کتابخانه‌ی requests در دسترس نیست"}
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length") or 0)
        done = 0
        with open(dest, "wb") as fh:
            for block in resp.iter_content(1 << 16):
                if not block:
                    continue
                fh.write(block)
                done += len(block)
                _write_state(cfg, downloading=True, file=dest.name,
                             percent=round(done * 100 / total) if total else 0,
                             downloaded=done, total=total)
    except Exception as exc:  # noqa: BLE001
        _write_state(cfg, downloading=False, error=str(exc))
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    if sha256 and sha256_of(dest).lower() != sha256.lower():
        _write_state(cfg, downloading=False, error="امضای فایل درست نیست")
        return {"ok": False, "error": "امضای فایل (sha256) با مانیفست یکی نیست"}
    _write_state(cfg, downloading=False, percent=100, file=dest.name,
                 downloaded=dest.stat().st_size, total=dest.stat().st_size)
    return {"ok": True, "path": str(dest), "size": dest.stat().st_size}


# --------------------------------------------------------------------------- #
# نصب
# --------------------------------------------------------------------------- #
def install_android(apk: Path) -> dict:
    """درخواست نصب APK از سیستم اندروید (صفحه‌ی نصب باز می‌شود)."""
    try:
        from jnius import autoclass  # فقط داخل بسته‌ی اندروید موجود است
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"jnius در دسترس نیست: {exc}"}

    try:
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        File = autoclass("java.io.File")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        context = activity.getApplicationContext()

        jfile = File(str(apk))
        uri = None
        # اندروید ۷ به بالا: مسیر فایل را نمی‌توان مستقیم داد؛ باید FileProvider باشد
        for provider, authority in (
            ("androidx.core.content.FileProvider", None),
            ("android.support.v4.content.FileProvider", None),
        ):
            try:
                FileProvider = autoclass(provider)
                auth = authority or f"{context.getPackageName()}.fileprovider"
                uri = FileProvider.getUriForFile(context, auth, jfile)
                if uri is not None:
                    break
            except Exception:  # noqa: BLE001
                continue
        if uri is None:  # تلاشِ آخر (اندرویدهای قدیمی)
            uri = Uri.fromFile(jfile)

        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(uri, "application/vnd.android.package-archive")
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        activity.startActivity(intent)
        return {"ok": True, "message": "صفحه‌ی نصب باز شد؛ روی Install بزنید"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def install_windows(path: Path) -> dict:
    """اجرای نصب‌کننده‌ی ویندوزی (خودش جایگزین نسخه‌ی قبلی می‌شود)."""
    try:
        if os.name == "nt":
            os.startfile(str(path))  # noqa: S606
        else:
            subprocess.Popen([str(path)], shell=False)
        return {"ok": True, "message": "نصب‌کننده اجرا شد؛ مراحل را تأیید کنید"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def install(path: Path, key: str | None = None) -> dict:
    key = key or platform_key()
    if key == "android":
        return install_android(Path(path))
    if key == "windows":
        return install_windows(Path(path))
    return {"ok": False, "error": f"نصب خودکار روی این سکو ({key}) پشتیبانی نمی‌شود"}


# --------------------------------------------------------------------------- #
# یک فرایند کامل: بررسی → دانلود → نصب
# --------------------------------------------------------------------------- #
def update(cfg, key: str | None = None, auto_install: bool = True,
           background: bool = False) -> dict:
    key = key or platform_key()
    info = check_update(cfg, key)
    if not info["ok"]:
        _write_state(cfg, error=info["error"], downloading=False)
        return info
    if not info["has_update"]:
        _write_state(cfg, message="برنامه به‌روز است", downloading=False,
                     latest=info["latest"])
        return {**info, "message": "برنامه به‌روز است"}

    asset = info.get("asset") or {}
    url = asset.get("url") or ""
    if not url:
        return {**info, "ok": False, "error": "آدرس فایل نصب در مانیفست نیست"}

    dest = Path(cfg.outbox_dir) / "updates" / (asset.get("file") or
                                               ("frilanser.apk" if key == "android"
                                                else "Frilanser-Setup.exe"))
    res = download(cfg, url, dest, asset.get("sha256") or "")
    if not res["ok"]:
        return {**info, **res}

    out = {**info, "downloaded": res["path"], "size": res["size"]}
    if auto_install:
        ins = install(dest, key)
        out.update(ins)
        _write_state(cfg, installed=bool(ins.get("ok")), message=ins.get("message")
                     or ins.get("error", ""), downloading=False)
    else:
        out["message"] = f"فایل آماده است: {dest}"
        _write_state(cfg, message=out["message"], downloading=False)
    return out


def update_async(cfg, key: str | None = None) -> dict:
    """اجرا در نخِ پس‌زمینه (برای اینکه رابط کاربری قفل نشود)."""
    _write_state(cfg, downloading=True, percent=0, message="در حال بررسی…", error="")
    thread = threading.Thread(target=update, args=(cfg, key), daemon=True)
    thread.start()
    return {"ok": True, "message": "به‌روزرسانی در پس‌زمینه شروع شد"}
