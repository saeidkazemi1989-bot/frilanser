"""پیشنهادِ بهتر (Upsell): به‌جای «آنچه کارفرما خواسته»، راه‌حلی بهتر پیشنهاد بده.

نمونه‌ی واقعیِ این سناریو: کارفرما یک «فایل اکسل» خواسته است. اکسل برای این کار
بد نیست، اما زود از کنترل خارج می‌شود: نسخه‌ها با هم فرق می‌کنند، چند نفر
نمی‌توانند هم‌زمان روی آن کار کنند، فرمول‌ها با یک جابه‌جاییِ سطر خراب می‌شوند و
هر تغییرِ کوچکی یعنی فرستادنِ فایلِ تازه برای همه.

این ماژول:

۱. تشخیص می‌دهد کارفرما دقیقاً چه خواسته (اکسل / ورد / پاورپوینت / دستی …).
۲. یک جایگزینِ مشخص پیشنهاد می‌کند (مثلاً «یک برنامه‌ی سبکِ تحت‌وب»).
۳. دلیل می‌آورد که چرا جایگزین بهتر است (به زبانِ کارفرما، نه فنی).
۴. قیمتِ هر دو گزینه را می‌گذارد تا کارفرما خودش انتخاب کند.
۵. یک متنِ آماده‌ی کپی‌کردن می‌سازد برای فرستادن به کارفرما.

هیچ‌چیز به‌طور خودکار برای کارفرما فرستاده نمی‌شود؛ ارسالِ پیشنهاد در سایت
همیشه دستی و با خودِ شماست (همان‌طور که خواسته‌اید).
"""

from __future__ import annotations

import re
from typing import Any

# --------------------------------------------------------------------------- #
# تشخیصِ خواسته‌ی کارفرما → جایگزینِ بهتر
# --------------------------------------------------------------------------- #
# هر مدخل: (الگو در متنِ آگهی، آنچه کارفرما خواسته، جایگزینِ پیشنهادی،
#           ضریبِ زمان برای جایگزین)
REQUESTS: tuple[tuple[str, str, str, float], ...] = (
    (r"اکسل|excel|xlsx|صفحه\s*گسترده|sheet",
     "یک فایل اکسل",
     "یک برنامه‌ی سبکِ تحت‌وب (فرمِ ورودِ داده + جدولِ زنده + خروجی اکسل)",
     1.35),
    (r"اکسس|access\s*(?:دیتابیس|پایگاه)?",
     "یک پایگاه‌داده‌ی اکسس",
     "یک برنامه‌ی تحت‌وب با پایگاه‌داده‌ی امن و دسترسیِ سطح‌بندی‌شده",
     1.4),
    (r"ورد|word\s*file|فایل\s*word|doc(x)?\b",
     "یک فایل ورد",
     "یک قالبِ تحت‌وب که خروجیِ ورد و پی‌دی‌افِ تمیز می‌سازد",
     1.25),
    (r"پاورپوینت|powerpoint|ppt(x)?\b|ارائه",
     "یک فایل پاورپوینت",
     "یک ارائه‌ی تعاملیِ تحت‌وب که روی موبایل هم درست دیده می‌شود",
     1.3),
    (r"فرم\s*(?:کاغذی|دستی)|کاغذ|دستی\s*پر\s*کن",
     "فرمِ کاغذی یا فایلِ دستی",
     "یک فرمِ آنلاین که داده‌ها را مستقیم و بی‌غلط جمع می‌کند",
     1.3),
    (r"پی‌دی‌اف|pdf\b",
     "یک فایل پی‌دی‌اف",
     "یک صفحه‌ی تحت‌وب که همان محتوا را با لینک و جست‌وجو نشان می‌دهد",
     1.2),
)

DEFAULT_WANT = "یک فایل یا خروجیِ ایستا"
DEFAULT_ALT = ("یک برنامه‌ی سبکِ تحت‌وب که همان کار را سریع‌تر، دقیق‌تر و "
               "برای همه‌ی افرادِ تیم انجام می‌دهد")

# دلیل‌هایی که کارفرما می‌فهمد (نه توضیحِ فنی)
REASONS = (
    "همه هم‌زمان روی یک نسخه کار می‌کنند؛ دیگر «کدام فایل جدیدتر است؟» پیش نمی‌آید.",
    "ورودِ داده با فرم انجام می‌شود، برای همین غلطِ تایپی و خراب شدنِ فرمول‌ها از بین می‌رود.",
    "هر وقت خواستید خروجیِ اکسل بگیرید؛ خروجی همیشه به‌روز است، نه نسخه‌ی هفته‌ی پیش.",
    "روی موبایل و کامپیوتر باز می‌شود و نیازی به نصب نیست.",
    "گزارش و جست‌وجو در لحظه انجام می‌شود، بدون مرتب‌کردنِ دستی.",
)


def detect_request(text: str) -> dict:
    """خواسته‌ی کارفرما را از متنِ آگهی تشخیص می‌دهد."""
    body = (text or "").lower()
    for pattern, want, alternative, factor in REQUESTS:
        if re.search(pattern, body, re.I):
            return {"wanted": want, "alternative": alternative,
                    "hours_factor": factor, "matched": pattern}
    return {"wanted": DEFAULT_WANT, "alternative": DEFAULT_ALT,
            "hours_factor": 1.3, "matched": ""}


def _round_to(value: float, step: int) -> int:
    step = max(1, int(step or 1))
    return int(round(value / step) * step)


def build_upsell(project: Any, cfg: Any, proposal: dict | None = None) -> dict:
    """پیشنهادِ بهتر را برای یک پروژه می‌سازد (بدون ارسالِ خودکار)."""
    text = f"{project.title or ''}\n{project.description or ''}"
    found = detect_request(text)

    hours = float((proposal or {}).get("hours") or 0) or 0.0
    rate = float(cfg.pricing.get("hourly_rate_toman", 450000) or 450000)
    round_to = int(cfg.pricing.get("round_to_toman", 500000) or 500000)
    min_price = int(cfg.pricing.get("min_project_price_toman", 5_000_000) or 5_000_000)

    # زمان و قیمتِ جایگزین: کمی بیشتر از خواسته‌ی اولیه (چون ارزشش بیشتر است)
    alt_hours = round(max(6.0, (hours or 8.0) * float(found["hours_factor"])), 1)
    alt_price = max(min_price, _round_to(alt_hours * rate, round_to))
    base_price = int((proposal or {}).get("price") or 0)

    return {
        "wanted": found["wanted"],
        "alternative": found["alternative"],
        "reasons": list(REASONS),
        "hours": alt_hours,
        "price": alt_price,
        "base_price": base_price,
        "diff": alt_price - base_price if base_price else 0,
        "text": upsell_text(project=project, wanted=found["wanted"],
                            alternative=found["alternative"],
                            alt_price=alt_price, base_price=base_price,
                            alt_hours=alt_hours,
                            schedule_days=(proposal or {}).get("schedule_days") or 0),
    }


def upsell_text(project: Any, wanted: str, alternative: str, alt_price: int,
                base_price: int, alt_hours: float, schedule_days: int = 0) -> str:
    """متنِ آماده برای فرستادن به کارفرما (دو گزینه، انتخاب با خودش)."""
    reasons = "\n".join(f"   • {r}" for r in REASONS)
    lines = [
        f"در مورد «{project.title}»:",
        "",
        f"شما {wanted} خواسته‌اید. انجامش می‌دهم، اما یک گزینه‌ی بهتر هم هست "
        "که فکر می‌کنم به نفعِ شماست؛ خودتان انتخاب کنید:",
        "",
        f"گزینه‌ی ۱ — همان‌طور که خواستید ({wanted}):",
        f"   • مبلغ: {base_price:,} تومان" if base_price else "   • مبلغ: توافقی",
        "   • همان خروجی که مشخص کرده‌اید، تحویل می‌شود.",
        "",
        f"گزینه‌ی ۲ — پیشنهادِ من ({alternative}):",
        f"   • مبلغ: {alt_price:,} تومان (حدود {alt_hours:g} ساعت کار)",
        f"   • زمانِ تحویل: حدود {schedule_days} روز" if schedule_days else "",
        "   • مزیت‌ها:",
        reasons,
        "",
        "هر کدام را بخواهید همان را تحویل می‌دهم؛ فرقِ قیمت فقط برای ارزشِ "
        "اضافه‌ای است که گزینه‌ی دوم برای‌تان دارد.",
        "",
        "اگر گزینه‌ی دوم را انتخاب می‌کنید، می‌توانم پیش از شروع یک پیش‌نمایشِ "
        "کوتاه از شکلِ نهایی بفرستم تا دقیقاً ببینید چه چیزی تحویل می‌گیرید.",
    ]
    return "\n".join(line for line in lines if line != "")
