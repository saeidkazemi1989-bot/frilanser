"""نقطه‌ی ورود نسخه‌ی اندرویدیِ فریلنس‌یار.

این فایل توسط python-for-android (از طریق buildozer) با «بوت‌استرپ webview» اجرا
می‌شود: رابط برنامه همان داشبورد وبِ Flask است که روی خود گوشی (localhost) بالا
می‌آید و در یک WebView نمایش داده می‌شود. ترتیب کار:

    ۱) انتخاب یک پوشه‌ی قابل‌نوشتن برای داده‌ها (حافظه‌ی داخلی برنامه)
    ۲) کپی تنظیمات و اسنپ‌شات‌های همراهِ برنامه (اولین اجرا)
    ۳) اگر داده‌ای نبود، یک اسکن خودکار از اسنپ‌شات‌ها
    ۴) اجرای سرور وب روی پورت ۵۰۰۰ و ماندن در اجرا

پورت را می‌توان با متغیر محیطی FRILANSER_PORT تغییر داد (باید با p4a.port
در buildozer.spec یکی باشد).
"""

from __future__ import annotations

import os
import sys
import threading
import time

PORT = int(os.environ.get("FRILANSER_PORT", "5000") or 5000)
HOST = os.environ.get("FRILANSER_HOST", "127.0.0.1")


def _pick_home() -> str:
    """اولین پوشه‌ای که روی اندروید قابل نوشتن است را برمی‌گرداند."""
    candidates: list[str] = []

    try:  # python-for-android
        from android.storage import app_storage_path, primary_external_storage_path

        try:
            ext = primary_external_storage_path()
            if ext:
                # پوشه‌ی اختصاصیِ برنامه در حافظه‌ی خارجی (از مدیر فایل هم قابل دسترسی است)
                candidates.append(os.path.join(ext, "frilanser"))
        except Exception:  # noqa: BLE001
            pass
        try:
            internal = app_storage_path()
            if internal:
                candidates.append(os.path.join(internal, "frilanser"))
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001  (روی دسکتاپ: فقط برای تست)
        pass

    candidates += [
        os.path.join(os.path.expanduser("~"), "frilanser"),
        os.path.join("/tmp", "frilanser"),
    ]

    for cand in candidates:
        try:
            os.makedirs(cand, exist_ok=True)
            probe = os.path.join(cand, ".write-test")
            with open(probe, "w") as fh:
                fh.write("ok")
            os.remove(probe)
            return cand
        except OSError:
            continue
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _first_run_scan(cfg, store) -> None:
    """اگر هیچ آگهی‌ای نیست، از اسنپ‌شات‌های همراه برنامه می‌خوانیم."""
    try:
        if len(store.all()):
            return
    except Exception:  # noqa: BLE001
        return

    def worker():
        try:
            from frilanser import pipeline

            pipeline.run_all(cfg, store, offline=True, refresh=False,
                             demo_limit=3, force=False)
        except Exception as exc:  # noqa: BLE001
            print(f"[frilanser] اسکن اولیه ناموفق بود: {exc!r}")

    threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    home = _pick_home()
    os.environ["FRILANSER_HOME"] = home
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from frilanser.config import bootstrap_user_files, load_config
    from frilanser.store import Store
    from frilanser.web.app import create_app

    cfg = load_config()
    bootstrap_user_files(cfg)
    store = Store(cfg.data_dir)

    _first_run_scan(cfg, store)

    app = create_app(cfg, store)
    print(f"[frilanser] سرور روی http://{HOST}:{PORT} — پوشه‌ی داده: {home}")
    sys.stdout.flush()

    # روی اندروید گاهی اتصالِ WebView کمی دیرتر آماده می‌شود؛ سرور را زودتر بالا می‌آوریم
    try:
        app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)
    except OSError:
        print("[frilanser] بستن روی 127.0.0.1 ناموفق بود؛ تلاش با 0.0.0.0")
        app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True,
                use_reloader=False)


if __name__ == "__main__":
    main()
