"""نقطه‌ی ورود نسخه‌ی اندرویدیِ فریلنس‌یار.

این فایل توسط python-for-android (از طریق buildozer) با «بوت‌استرپ webview» اجرا
می‌شود: رابط برنامه همان داشبورد وبِ Flask است که روی خود گوشی (localhost) بالا
می‌آید و در یک WebView نمایش داده می‌شود.

**ضدِخطا بودن**: هیچ استثنایی نباید باعث بسته شدن برنامه شود. اگر مرحله‌ای شکست
بخورد، خطا در فایل `crash.log` (در پوشه‌ی داده‌ها) نوشته می‌شود و یک صفحه‌ی خطا
با همان پیام روی پورتِ برنامه نمایش داده می‌شود تا کاربر بتواند آن را ارسال کند.
صفحه‌ی `/crash-log` همیشه آخرین خطا را نشان می‌دهد.
"""

from __future__ import annotations

import os
import sys
import threading
import traceback

PORT = int(os.environ.get("FRILANSER_PORT", "5000") or 5000)
HOST = os.environ.get("FRILANSER_HOST", "127.0.0.1")

# لاگ خطاهای راه‌اندازی — در پوشه‌ی داده‌ها نوشته می‌شود
CRASH_LOG = "crash.log"


def _log(msg: str) -> None:
    try:
        sys.stderr.write(f"[frilanser] {msg}\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001
        pass


def _crash_path() -> str:
    home = os.environ.get("FRILANSER_HOME") or ""
    return os.path.join(home, CRASH_LOG) if home else CRASH_LOG


def _record_crash(title: str, exc: BaseException) -> str:
    """متن کامل خطا را در فایل می‌نویسد و برمی‌گرداند."""
    text = f"{title}: {type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
    try:
        path = _crash_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except Exception:  # noqa: BLE001
        pass
    _log(text)
    return text


# --------------------------------------------------------------------------- #
# انتخاب پوشه‌ی داده
# --------------------------------------------------------------------------- #
def _candidate_dirs() -> list[str]:
    """فهرست پوشه‌های پیشنهادی برای داده‌ها (اولی‌ها ترجیح دارند)."""
    cands: list[str] = []

    def add(path) -> None:
        if path:
            cands.append(str(path))

    try:  # python-for-android
        from android.storage import app_storage_path, primary_external_storage_path

        try:
            ext = primary_external_storage_path()
            if ext:
                # پوشه‌ی اختصاصی برنامه در حافظه‌ی خارجی (از مدیر فایل هم در دسترس است)
                add(os.path.join(ext, "frilanser"))
        except Exception as exc:  # noqa: BLE001
            _log(f"حافظه‌ی خارجی در دسترس نیست: {exc!r}")
        try:
            internal = app_storage_path()
            if internal:
                add(os.path.join(internal, "frilanser"))
        except Exception as exc:  # noqa: BLE001
            _log(f"حافظه‌ی داخلی در دسترس نیست: {exc!r}")
    except Exception as exc:  # noqa: BLE001  (روی دسکتاپ یا بدون ماژول android)
        _log(f"ماژول android در دسترس نیست: {exc!r}")

    # پوشه‌ی فایل‌های برنامه (روی اندروید: /data/data/<pkg>/files) — همیشه قابل نوشتن
    app_path = os.environ.get("ANDROID_APP_PATH") or os.environ.get("ANDROID_ARGUMENT")
    if app_path:
        add(os.path.join(os.path.dirname(str(app_path)), "frilanser"))
        add(os.path.join(str(app_path), "frilanser"))

    add(os.path.join(os.path.expanduser("~"), "frilanser"))

    import tempfile

    add(os.path.join(tempfile.gettempdir(), "frilanser"))
    return cands


def _writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write-test")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
        return True
    except Exception as exc:  # noqa: BLE001
        _log(f"پوشه قابل نوشتن نیست ({path}): {exc!r}")
        return False


def pick_home() -> str:
    """اولین پوشه‌ای که واقعاً قابل نوشتن است را برمی‌گرداند."""
    for cand in _candidate_dirs():
        if _writable(cand):
            _log(f"پوشه‌ی داده انتخاب شد: {cand}")
            return cand
    import tempfile

    fallback = tempfile.mkdtemp(prefix="frilanser-")
    _log(f"هیچ پوشه‌ای قابل نوشتن نبود؛ استفاده از: {fallback}")
    return fallback


# --------------------------------------------------------------------------- #
# سرورِ خطا (اگر راه‌اندازی شکست خورد، همین بالا می‌آید)
# --------------------------------------------------------------------------- #
ERROR_PAGE = """<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>خطا در اجرای برنامه</title>
<style>
 body{{margin:0;background:#0b1220;color:#e7ecf5;font-family:Tahoma,sans-serif;padding:18px}}
 h1{{font-size:18px;color:#fda4af}} .box{{background:#141c2e;border:1px solid #22304a;
 border-radius:14px;padding:14px;margin-top:12px;font-size:13px;line-height:1.9}}
 pre{{direction:ltr;text-align:left;background:#0f172a;color:#cbd5e1;padding:12px;
 border-radius:10px;overflow:auto;font-size:11.5px;white-space:pre-wrap}}
</style></head><body>
<h1>⚠️ برنامه نتوانست کامل بالا بیاید</h1>
<div class="box">این متن را کپی یا عکس بگیرید و برای پشتیبانی بفرستید تا مشکل برطرف شود.
<br>مسیر لاگ: <code dir="ltr">{home}/{log}</code></div>
<div class="box"><b>جزئیات خطا:</b><pre>{error}</pre></div>
</body></html>
"""


def _serve_error(error_text: str, home: str) -> None:
    """یک سرورِ خیلی ساده که فقط متن خطا را نشان می‌دهد (وابستگی ندارد)."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    body = ERROR_PAGE.format(error=error_text, home=home, log=CRASH_LOG).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except Exception:  # noqa: BLE001
                pass

        def log_message(self, *args):  # noqa: A002
            pass

    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except Exception:  # noqa: BLE001
        try:
            ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
# راه‌اندازی
# --------------------------------------------------------------------------- #
def _first_run_scan(cfg, store) -> None:
    """اگر هیچ آگهی‌ای نیست، از اسنپ‌شات‌های همراه برنامه می‌خوانیم."""
    try:
        if len(store.all()):
            return
    except Exception:  # noqa: BLE001
        return

    def worker() -> None:
        try:
            from frilanser import pipeline

            pipeline.run_all(cfg, store, offline=True, refresh=False,
                             demo_limit=3, force=False)
        except Exception as exc:  # noqa: BLE001
            _log(f"اسکن اولیه ناموفق بود: {exc!r}")

    threading.Thread(target=worker, daemon=True).start()


def boot():
    """آماده‌سازی برنامه؛ در صورت خطا، پیام خطا را برمی‌گرداند."""
    home = pick_home()
    os.environ["FRILANSER_HOME"] = home

    here = os.path.dirname(os.path.abspath(__file__))
    for path in (here, os.path.dirname(here)):
        if path and path not in sys.path:
            sys.path.insert(0, path)

    try:
        from frilanser.config import bootstrap_user_files, load_config
        from frilanser.store import Store
        from frilanser.web.app import create_app
    except Exception as exc:  # noqa: BLE001
        return None, home, _record_crash("خطا در import ماژول‌های برنامه", exc)

    try:
        cfg = load_config()
    except Exception as exc:  # noqa: BLE001
        return None, home, _record_crash("خطا در خواندن تنظیمات", exc)

    try:
        bootstrap_user_files(cfg)
    except Exception as exc:  # noqa: BLE001
        _record_crash("هشدار: کپی فایل‌های اولیه ناموفق بود", exc)

    try:
        store = Store(cfg.data_dir)
    except Exception as exc:  # noqa: BLE001
        return None, home, _record_crash("خطا در باز کردن پایگاه داده", exc)

    try:
        app = create_app(cfg, store)
        _first_run_scan(cfg, store)
        return app, home, None
    except Exception as exc:  # noqa: BLE001
        return None, home, _record_crash("خطا در ساخت داشبورد", exc)


def main() -> None:
    app, home, error = boot()
    if app is None or error:
        _serve_error(error or "دلیل خطا مشخص نیست", home)
        return

    _log(f"سرور روی http://{HOST}:{PORT} — پوشه‌ی داده: {home}")
    try:
        app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)
    except OSError as exc:
        _record_crash("خطا در اتصال روی 127.0.0.1", exc)
        _log("بستن روی 127.0.0.1 ناموفق بود؛ تلاش با 0.0.0.0")
        try:
            app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True,
                    use_reloader=False)
        except Exception as exc2:  # noqa: BLE001
            _serve_error(_record_crash("سرور اجرا نشد", exc2), home)
    except Exception as exc:  # noqa: BLE001
        _serve_error(_record_crash("خطای غیرمنتظره در سرور", exc), home)


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:  # noqa: BLE001 - هیچ‌وقت نباید بسته شویم
        text = _record_crash("خطای پیش‌بینی‌نشده در اجرا", exc)
        try:
            _serve_error(text, os.environ.get("FRILANSER_HOME", ""))
        except Exception:  # noqa: BLE001
            pass
