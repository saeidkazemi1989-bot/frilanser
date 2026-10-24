"""به‌روزرسانیِ درون‌برنامه‌ای (بدون نیاز به مراجعه‌ی دستی به گیت‌هاب).

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
    """ماژولِ requests اگر واقعاً قابل استفاده باشد (همراهِ وابستگی‌هایش)."""
    try:
        import requests  # وابستگی پروژه
        import urllib3  # noqa: F401  # requests بدون urllib3 بالا نمی‌آید
    except Exception:  # noqa: BLE001
        return None
    return requests


def _http_get_json(url: str, timeout: float = 15.0) -> dict:
    """خواندنِ JSON از اینترنت — با requests یا با کتابخانه‌ی استاندارد."""
    requests = _request()
    if requests is not None:
        try:
            resp = requests.get(url, timeout=timeout,
                                headers={"Cache-Control": "no-cache"})
            if resp.status_code != 200:
                return {"ok": False, "status": resp.status_code, "data": None,
                        "how": "requests"}
            return {"ok": True, "status": 200, "data": resp.json(), "how": "requests"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "status": None, "data": None, "how": "requests",
                    "error": f"{type(exc).__name__}: {exc}"}
    from . import http

    got = http.get_json(url, timeout=timeout)
    return {"ok": bool(got.get("ok")), "status": got.get("status"),
            "data": got.get("data"), "how": got.get("how", "stdlib"),
            "error": got.get("error", "")}


def _http_download(url: str, dest, progress=None) -> dict:
    """دانلود فایل — با requests یا با کتابخانه‌ی استاندارد."""
    from . import http

    return http.download_file(url, dest, progress=progress)


def _cfg_value(cfg, key: str, default: str = "") -> str:
    try:
        return str(cfg.raw.get("update", {}).get(key, default) or default)
    except Exception:  # noqa: BLE001
        return default


# مانیفست روی یک CDN عمومی: در شبکه‌هایی که دسترسی به raw.githubusercontent.com
# بسته است (مثل ایران)، این آدرس معمولاً در دسترس است.
DEFAULT_CDN_MANIFEST = (
    f"https://cdn.jsdelivr.net/gh/{REPO_OWNER}/{REPO_NAME}@{DEFAULT_BRANCH}/{MANIFEST_REL}"
)
UPDATE_CONFIG_FILE = "update-config.json"


def _config_path(cfg) -> Path:
    return Path(cfg.outbox_dir) / UPDATE_CONFIG_FILE


def load_update_config(cfg) -> dict:
    """تنظیماتِ به‌روزرسانی که کاربر در برنامه تغییر داده است (مثل آدرسِ دلخواه)."""
    try:
        return json.loads(_config_path(cfg).read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_update_config(cfg, **fields) -> dict:
    data = load_update_config(cfg)
    data.update({k: v for k, v in fields.items()})
    try:
        _config_path(cfg).parent.mkdir(parents=True, exist_ok=True)
        _config_path(cfg).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    except OSError:
        pass
    return data


def _cdn_alternatives(url: str) -> list[str]:
    """هم‌زادهای همان آدرس روی CDNهای دیگر (هر کدام در دسترس بود استفاده می‌شود)."""
    alts = []
    if "cdn.jsdelivr.net" in url:
        alts.append(url.replace("cdn.jsdelivr.net", "gcore.jsdelivr.net"))
    return alts


def asset_urls(asset: dict) -> list[str]:
    """همه‌ی آدرس‌های ممکن برای یک فایل نصب، به ترتیبِ اولویت.

    ترتیب: CDN عمومی (و هم‌زادهایش) → آینه‌ی روی شاخه (raw) → لینکِ انتشارِ گیت‌هاب.
    """
    urls: list[str] = []
    for key in ("cdn", "mirror", "url"):
        value = str((asset or {}).get(key) or "").strip()
        if not value:
            continue
        for candidate in [value, *_cdn_alternatives(value)]:
            if candidate not in urls:
                urls.append(candidate)
    return urls


def _cdn_manifest_urls() -> list[str]:
    """چند CDN عمومی که فایل‌های مخزن را مستقیم سرو می‌کنند."""
    return [
        f"https://cdn.jsdelivr.net/gh/{REPO_OWNER}/{REPO_NAME}@{DEFAULT_BRANCH}/{MANIFEST_REL}",
        f"https://gcore.jsdelivr.net/gh/{REPO_OWNER}/{REPO_NAME}@{DEFAULT_BRANCH}/{MANIFEST_REL}",
        f"https://raw.githack.com/{REPO_OWNER}/{REPO_NAME}/{DEFAULT_BRANCH}/{MANIFEST_REL}",
    ]


def manifest_urls(cfg) -> list[str]:
    """فهرست آدرس‌هایی که برای یافتن مانیفست امتحان می‌شوند.

    اولویت: آدرسِ دستیِ کاربر ← آدرس‌های config.toml ← CDN ← شاخه (raw).
    """
    saved = str(load_update_config(cfg).get("manifest_url") or "").strip()
    cfg_single = _cfg_value(cfg, "manifest_url", "")
    cfg_list = (cfg.raw.get("update", {}) or {}).get("manifest_urls") or []
    if isinstance(cfg_list, str):
        cfg_list = [cfg_list]
    urls = [saved, cfg_single, *[str(u) for u in cfg_list],
            *_cdn_manifest_urls(), DEFAULT_MANIFEST_URL]
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
            "mirror": asset.get("mirror", ""),
            "cdn": asset.get("cdn", ""),
            "size": int(asset.get("size") or 0),
            "sha256": asset.get("sha256") or "",
            "urls": asset_urls(asset),
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


def _safe_check(cfg, key: str, timeout: int) -> dict:
    """بدنه‌ی بررسی نسخه — هر استثنایی به‌صورت پیام برگردانده می‌شود."""
    import traceback

    try:
        return _check_update_inner(cfg, key, timeout)
    except Exception as exc:  # noqa: BLE001
        import traceback as _tb

        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "trace": _tb.format_exc(), "current": __version__, "platform": key,
                "latest": __version__, "has_update": False, "notes": [], "asset": {},
                "release_url": "", "source": ""}


def check_update(cfg, key: str | None = None, timeout: int = 15) -> dict:
    """بررسی نسخه — همیشه JSON برمی‌گرداند (هرگز استثنا نمی‌دهد)."""
    return _safe_check(cfg, key or platform_key(), timeout)


def _check_update_inner(cfg, key: str, timeout: int) -> dict:
    """نسخه‌ی موجود را بررسی می‌کند (بدون تغییر در برنامه)."""
    key = key or platform_key()
    result = {"ok": False, "error": "", "current": __version__, "platform": key,
              "latest": __version__, "has_update": False, "notes": [], "asset": {},
              "release_url": "", "source": ""}

    # نکته: برای دریافت هم requests را امتحان می‌کنیم و هم کتابخانه‌ی استاندارد را،
    # چون در بعضی بسته‌ها requests بدون وابستگی‌هایش بسته‌بندی شده است.
    found: dict | None = None
    last_error = ""
    tried: list[str] = []
    for url in manifest_urls(cfg):
        got = _http_get_json(url, timeout=timeout)
        tried.append(url)
        if got.get("ok") and isinstance(got.get("data"), dict):
            found = _from_manifest(got["data"], key)
            if found:
                found["source"] = url
                found["how"] = got.get("how", "")
                break
        elif got.get("error"):
            last_error = f"{got.get('error')} ({got.get('how','')})"

    if not found:
        got = _http_get_json(RELEASE_API, timeout=timeout)
        tried.append(RELEASE_API)
        if got.get("ok") and isinstance(got.get("data"), dict):
            found = _from_release_api(got["data"], key)
            if found:
                found["source"] = RELEASE_API
                found["how"] = got.get("how", "")
        elif got.get("error"):
            last_error = f"{got.get('error')} ({got.get('how','')})"

    result["tried"] = tried

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


def download(cfg, url, dest: Path, sha256: str = "") -> dict:
    """دانلود فایل از یکی از آدرس‌های ممکن (هر کدام جواب داد همان)."""
    urls = [url] if isinstance(url, str) else list(url or [])
    urls = [u for u in urls if u]
    if not urls:
        return {"ok": False, "error": "هیچ آدرسی برای دانلود مشخص نشده"}
    errors: list[str] = []
    for candidate in urls:
        result = _download_one(cfg, candidate, Path(dest), sha256)
        if result.get("ok"):
            return {**result, "url": candidate}
        errors.append(f"{candidate} → {result.get('error')}")
        print(f"  ! دانلود از {candidate} ناموفق بود: {result.get('error')}")
    return {"ok": False, "error": " | ".join(errors), "tried": urls}


def _download_one(cfg, url: str, dest: Path, sha256: str = "") -> dict:
    """دانلود فایل با ذخیره‌ی وضعیت پیشرفت (برای نمایش در رابط کاربری)."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _progress(done: int, total: int) -> None:
        _write_state(cfg, downloading=True, file=dest.name,
                     percent=round(done * 100 / total) if total else 0,
                     downloaded=done, total=total)

    requests = _request()
    error = "requests در دسترس نیست"
    downloaded = False
    how = "requests"
    if requests is not None:
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
                    _progress(done, total)
            downloaded = True
            how = "requests"
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            how = "requests"

    # تلاش با کتابخانه‌ی استاندارد (وقتی requests ناقص بسته‌بندی شده باشد)
    if not downloaded:
        got = _http_download(url, dest, progress=_progress)
        if got.get("ok"):
            downloaded = True
            how = got.get("how", "stdlib")
        else:
            _write_state(cfg, downloading=False, error=str(got.get("error") or error))
            return {"ok": False, "error": f"{error} | {got.get('error')}",
                    "how": got.get("how", "stdlib")}

    if sha256 and sha256_of(dest).lower() != sha256.lower():
        _write_state(cfg, downloading=False, error="امضای فایل درست نیست")
        return {"ok": False, "error": "امضای فایل (sha256) با مانیفست یکی نیست"}
    _write_state(cfg, downloading=False, percent=100, file=dest.name,
                 downloaded=dest.stat().st_size, total=dest.stat().st_size)
    return {"ok": True, "path": str(dest), "size": dest.stat().st_size, "how": how}


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


def install_via_download_manager(url: str, filename: str, title: str = "") -> dict:
    """دانلود با «مدیر دانلود» اندروید و نمایش اعلان نصب.

    این روش نیازی به FileProvider ندارد (برخلاف نصب مستقیم فایل محلی روی
    اندروید ۷ به بالا) و روی همه‌ی گوشی‌ها کار می‌کند.
    """
    try:
        from jnius import autoclass
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"jnius در دسترس نیست: {exc}"}
    try:
        Uri = autoclass("android.net.Uri")
        Request = autoclass("android.app.DownloadManager$Request")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        dm = activity.getSystemService("download")

        req = Request(Uri.parse(url))
        req.setTitle(title or "به‌روزرسانی فریلنس‌یار")
        req.setDescription("پس از اتمام دانلود، روی اعلان بزنید و Install را انتخاب کنید")
        req.setNotificationVisibility(Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
        req.setDestinationInExternalPublicDir("Download", filename)
        req.setMimeType("application/vnd.android.package-archive")
        dm.enqueue(req)
        return {"ok": True,
                "message": "در حال دانلود؛ پس از اتمام، روی اعلان بزنید و Install را بزنید"}
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
    candidates = asset_urls(asset)
    url = candidates[0] if candidates else ""
    if not url:
        return {**info, "ok": False, "error": "آدرس فایل نصب در مانیفست نیست"}

    if key == "android" and auto_install:
        # روی اندروید، ساده‌ترین و مطمئن‌ترین راه: مدیر دانلودِ خود سیستم
        dm_res = install_via_download_manager(
            url, asset.get("file") or "frilanser.apk", title="به‌روزرسانی فریلنس‌یار")  # noqa: E501
        if dm_res.get("ok"):
            _write_state(cfg, downloading=False, message=dm_res["message"])
            return {**info, **dm_res}
        _write_state(cfg, downloading=True, message="مدیر دانلود در دسترس نبود؛ دانلود مستقیم…")

    dest = Path(cfg.outbox_dir) / "updates" / (asset.get("file") or
                                               ("frilanser.apk" if key == "android"
                                                else "Frilanser-Setup.exe"))
    res = download(cfg, candidates, dest, asset.get("sha256") or "")
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
