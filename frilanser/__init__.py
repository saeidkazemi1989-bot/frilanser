"""فریلنس‌یار آرنا — پیدا کردن، غربال کردن و قیمت‌گذاری پروژه‌های فریلنسری ایرانی.

هسته‌ی برنامه فقط از کتابخانه‌ی استاندارد پایتون استفاده می‌کند تا روی هر
سیستمی اجرا شود. داشبورد وب و دریافت زنده از سایت‌ها به پکیج‌های اختیاری
(Flask / requests / bs4) نیاز دارد.
"""

from __future__ import annotations

import os
import sys

__version__ = "1.0.0"

# اگر وابستگی‌ها در پوشه‌ی .pylib داخل ریپو نصب شده باشند (حالت قابل‌حمل)،
# آن را به مسیر ایمپورت اضافه می‌کنیم.
_PYLIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".pylib")
if os.path.isdir(_PYLIB) and _PYLIB not in sys.path:
    sys.path.insert(0, _PYLIB)
