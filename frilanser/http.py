"""دریافتِ اینترنتی **بدون وابستگی خارجی**.

در بعضی بسته‌ها (مثل APK ساخته‌شده با python-for-android) کتابخانه‌ی `requests`
هست اما وابستگی‌هایش (`urllib3`, `certifi`, …) نه؛ در نتیجه `import requests`
با خطا شکست می‌خورد و هم «دریافتِ آگهی از سایت‌ها» و هم «به‌روزرسانیِ برنامه»
از کار می‌افتادند.

این ماژول همان کار را با **کتابخانه‌ی استاندارد پایتون** انجام می‌دهد:

    get_text(url)      → متنِ صفحه (با رفعِ فشرده‌سازی و تشخیصِ رمزگذاری)
    get_json(url)      → خروجیِ JSON
    download_file(url) → ذخیره در فایل با گزارشِ پیشرفت

اگر `requests` و `certifi` در دسترس باشند ترجیح داده می‌شوند (پایدارترند)؛
در غیر این صورت مسیرِ استاندارد استفاده می‌شود. تأییدِ گواهی (SSL) پیش‌فرض
روشن است و فقط در صورتِ نبودِ گواهی‌های معتبرِ سیستم، با هشدار خاموش می‌شود.
"""

from __future__ import annotations

import gzip
import json
import ssl
import zlib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (
    HTTPSHandler,
    OpenerDirector,
    ProxyHandler,
    Request,
    build_opener,
)

DEFAULT_UA = (
    "Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Mobile Safari/537.36"
)


# --------------------------------------------------------------------------- #
# امکاناتِ موجود
# --------------------------------------------------------------------------- #
def has_requests() -> bool:
    """آیا requests واقعاً قابل استفاده است (همراهِ وابستگی‌هایش)؟"""
    try:
        import requests  # noqa: F401
        import urllib3  # noqa: F401  # requests بدون urllib3 کار نمی‌کند
    except Exception:  # noqa: BLE001
        return False
    return True


def has_certifi() -> bool:
    try:
        import certifi  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def ssl_context(verify: bool = True) -> ssl.SSLContext:
    """یک context با گواهی‌های معتبر (certifi اگر باشد، وگرنه گواهی‌های سیستم)."""
    context = ssl.create_default_context()
    if not verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    if has_certifi():
        try:
            import certifi

            context.load_verify_locations(certifi.where())
        except Exception:  # noqa: BLE001
            pass
    return context


# --------------------------------------------------------------------------- #
# تبدیلِ پاسخ به متن
# --------------------------------------------------------------------------- #
def _decode(raw: bytes, headers, default: str = "utf-8") -> str:
    """رفعِ فشرده‌سازی و تشخیصِ رمزگذاریِ پاسخ."""
    encoding = (headers.get("Content-Encoding") or "").lower()
    if "gzip" in encoding:
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    elif "deflate" in encoding:
        try:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        except zlib.error:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                pass
    elif "br" in encoding:
        try:
            import brotli  # type: ignore  # noqa: F401

            raw = brotli.decompress(raw)
        except Exception:  # noqa: BLE001 - brotli معمولاً در دسترس نیست
            pass

    charset = default
    content_type = (headers.get("Content-Type") or "").lower()
    for marker in ("charset=", "charset ="):
        if marker in content_type:
            charset = content_type.split(marker, 1)[1].split(";")[0].strip().strip('"\'')
            break
    else:
        head = raw[:2048].decode("ascii", "ignore").lower()
        for pattern in ('charset="', "charset='"):
            if pattern in head:
                charset = head.split(pattern, 1)[1].split('"')[0].split("'")[0].strip()
                break
        else:
            if "charset=" in head:
                charset = head.split("charset=", 1)[1].split()[0].strip().strip('\'"')
    for candidate in (charset, default, "utf-8", "windows-1256", "latin-1"):
        try:
            return raw.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")


def _opener(context: ssl.SSLContext | None = None) -> OpenerDirector:
    """بازکننده‌ای که از context مشخص برای HTTPS استفاده می‌کند."""
    handlers: list = [ProxyHandler({})]      # پروکسیِ سیستم اگر باشد استفاده می‌شود
    if context is not None:
        handlers.append(HTTPSHandler(context=context))
    return build_opener(*handlers)


# --------------------------------------------------------------------------- #
# دریافتِ متن / JSON
# --------------------------------------------------------------------------- #
def get_text(url: str, timeout: float = 25.0, headers: dict | None = None,
             allow_insecure: bool = True) -> dict:
    """دریافتِ متن؛ خروجی {'ok','status','text','error','how'}.

    هرگز استثنا پرتاب نمی‌کند؛ برای نمایشِ علت در رابط کاربری مناسب است.
    """
    hdrs = {"User-Agent": DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.6"}
    hdrs.update({k: str(v) for k, v in (headers or {}).items() if v})

    # ---- مسیرِ اول: requests (اگر واقعاً سالم نصب شده باشد)
    if has_requests():
        try:
            import requests

            resp = requests.get(url, headers=hdrs, timeout=timeout)
            return {"ok": resp.status_code < 400, "status": resp.status_code,
                    "text": resp.text, "error": "" if resp.status_code < 400
                    else f"HTTP {resp.status_code}", "how": "requests"}
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            if not allow_insecure:
                return {"ok": False, "status": None, "text": "", "error": error,
                        "how": "requests"}
            # ادامه با کتابخانه‌ی استاندارد
        else:  # pragma: no cover
            pass

    # ---- مسیرِ دوم: کتابخانه‌ی استاندارد
    attempts = [True, False] if allow_insecure else [True]
    last_error = ""
    for verify in attempts:
        try:
            request = Request(url, headers=hdrs)
            with _opener(ssl_context(verify)).open(request, timeout=timeout) as resp:
                raw = resp.read()
                status = int(getattr(resp, "status", 0) or 0)
                if not status:
                    try:
                        status = int(resp.getcode() or 0)
                    except Exception:  # noqa: BLE001
                        status = 0
                return {"ok": True, "status": status, "error": "",
                        "text": _decode(raw, resp.headers),
                        "how": "stdlib" if verify else "stdlib (بدون تأیید گواهی)"}
        except HTTPError as exc:
            # سرور پاسخ داده اما کد موفق نیست — دوباره با گواهی تلاش نمی‌کنیم
            try:
                body = exc.read()
            except Exception:  # noqa: BLE001
                body = b""
            return {"ok": False, "status": int(getattr(exc, "code", 0) or 0),
                    "text": _decode(body, exc.headers or {}),
                    "error": f"HTTP {getattr(exc, 'code', '?')}", "how": "stdlib"}
        except (URLError, ssl.SSLError, OSError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if verify:
                continue        # شاید مشکل از گواهی باشد
    return {"ok": False, "status": None, "text": "", "error": last_error,
            "how": "stdlib"}


def get_json(url: str, timeout: float = 15.0, headers: dict | None = None) -> dict:
    """خروجیِ JSON یک نشانی (بدون پرتابِ استثنا)."""
    result = get_text(url, timeout=timeout, headers=headers)
    if not result["ok"]:
        return {"ok": False, "status": result.get("status"),
                "error": result.get("error", ""), "how": result.get("how", ""),
                "data": None}
    try:
        return {"ok": True, "status": result.get("status"), "error": "",
                "how": result.get("how", ""), "data": json.loads(result["text"])}
    except json.JSONDecodeError as exc:
        return {"ok": False, "status": result.get("status"),
                "error": f"پاسخ JSON نبود: {exc}", "how": result.get("how", ""),
                "data": None}


# --------------------------------------------------------------------------- #
# دانلودِ فایل
# --------------------------------------------------------------------------- #
def download_file(url: str, dest, timeout: float = 60.0,
                  headers: dict | None = None,
                  progress=None) -> dict:
    """دانلود فایل با گزارشِ پیشرفت (progress(done, total))."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if has_requests():
        try:
            import requests

            with requests.get(url, stream=True, timeout=timeout,
                              headers=headers or {}) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length") or 0)
                done = 0
                with open(dest, "wb") as fh:
                    for block in resp.iter_content(1 << 16):
                        if not block:
                            continue
                        fh.write(block)
                        done += len(block)
                        if progress:
                            progress(done, total)
            return {"ok": True, "path": str(dest), "size": dest.stat().st_size,
                    "how": "requests"}
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
        else:  # pragma: no cover
            last = ""
    else:
        last = "requests در دسترس نیست"

    for verify in (True, False):
        try:
            request = Request(url, headers={"User-Agent": DEFAULT_UA,
                                            **(headers or {})})
            with _opener(ssl_context(verify)).open(request, timeout=timeout) as resp:
                total = int(resp.headers.get("content-length") or 0)
                done = 0
                with open(dest, "wb") as fh:
                    while True:
                        block = resp.read(1 << 16)
                        if not block:
                            break
                        fh.write(block)
                        done += len(block)
                        if progress:
                            progress(done, total)
            return {"ok": True, "path": str(dest), "size": dest.stat().st_size,
                    "how": "stdlib" if verify else "stdlib (بدون تأیید گواهی)"}
        except (HTTPError, URLError, ssl.SSLError, OSError, ValueError) as exc:
            last = f"{type(exc).__name__}: {exc}"
            if verify:
                continue
    return {"ok": False, "error": last or "دانلود ناموفق بود", "path": str(dest)}


def describe() -> dict:
    """گزارشِ مسیرِ دریافت (برای عیب‌یابی روی دستگاه)."""
    return {
        "requests": has_requests(),
        "certifi": has_certifi(),
        "stdlib": True,
        "ssl": _ssl_info(),
        "host_example": urlparse("https://example.com").scheme,
    }


def _ssl_info() -> str:
    try:
        return f"OpenSSL {ssl.OPENSSL_VERSION}"
    except Exception:  # noqa: BLE001
        return "نامشخص"
