"""فریلنس‌یار آرنا — پیدا کردن، غربال کردن و قیمت‌گذاری پروژه‌های فریلنسری ایرانی.

هسته‌ی برنامه فقط از کتابخانه‌ی استاندارد پایتون استفاده می‌کند تا روی هر
سیستمی اجرا شود. داشبورد وب و دریافت زنده از سایت‌ها به پکیج‌های اختیاری
(Flask / requests / bs4) نیاز دارد.
"""

from __future__ import annotations

import os
import sys

__version__ = "1.0.0"

# ----------------------------------------------------------------------------
# خروجی استاندارد را روی UTF-8 می‌گذاریم؛ در ویندوز (کنسول و نسخه‌ی EXE)
# کدگذاری پیش‌فرض فارسی را پشتیبانی نمی‌کند و برنامه با خطا متوقف می‌شد.
# ----------------------------------------------------------------------------
def _force_utf8_streams() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # pragma: no cover
                pass


_force_utf8_streams()

# اگر وابستگی‌ها در پوشه‌ی .pylib داخل ریپو نصب شده باشند (حالت قابل‌حمل)،
# آن را به مسیر ایمپورت اضافه می‌کنیم.
_PYLIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".pylib")
if os.path.isdir(_PYLIB) and _PYLIB not in sys.path:
    sys.path.insert(0, _PYLIB)

# در نسخه‌ی اجرایی (PyInstaller) منابع داخل sys._MEIPASS هستند؛ path.py آن را تشخیص می‌دهد
FROZEN = bool(getattr(sys, "frozen", False))
