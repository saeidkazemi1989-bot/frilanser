"""تنظیماتِ پیش‌فرضِ منابع (سایت‌ها) — داخلِ خودِ برنامه.

چرا اینجا؟ چون اگر ``config.toml`` روی دستگاه خوانده نشود (یا نسخه‌ی قدیمی‌ای
از آن به‌جا مانده باشد که نشانی‌ها را ندارد)، منبع‌ها «هیچ نشانی‌ای» نخواهند
داشت و اسکن بدون این‌که خطایی بدهد صفر آگهی برمی‌گرداند — دقیقاً اتفاقی که
روی گوشی افتاد و در گزارش به شکلِ «تلاش‌ها: ۰» دیده شد.

این مقادیر فقط زمانی به کار می‌روند که در ``config.toml`` چیزی نباشد؛ تنظیماتِ
کاربر همیشه بر این پیش‌فرض‌ها مقدم است.
"""

from __future__ import annotations

DEFAULT_SOURCES: dict[str, dict] = {
    "ponisha": {
        "enabled": True,
        "label": "پونیشا",
        "base_url": "https://ponisha.ir",
        "listing_url": "https://ponisha.ir/search/projects",
        "project_url_prefix": "https://ponisha.ir/project/",
        "fee_note": "تسویه از طریق پلتفرم",
    },
    "karlancer": {
        "enabled": True,
        "label": "کارلنسر",
        "base_url": "https://www.karlancer.com",
        "listing_url": "https://www.karlancer.com/search",
        "project_url_prefix": "https://www.karlancer.com/projects/",
        "fee_note": "تسویه از طریق پلتفرم",
    },
    "karlancer_programming": {
        "enabled": True,
        "label": "کارلنسر - برنامه‌نویسی",
        "kind": "karlancer",
        "base_url": "https://www.karlancer.com",
        "listing_url": "https://www.karlancer.com/jobs/programming",
        "project_url_prefix": "https://www.karlancer.com/projects/",
        "fee_note": "تسویه از طریق پلتفرم",
    },
    "karlancer_web_design": {
        "enabled": True,
        "label": "کارلنسر - طراحی سایت",
        "kind": "karlancer",
        "base_url": "https://www.karlancer.com",
        "listing_url": "https://www.karlancer.com/jobs/web-design",
        "project_url_prefix": "https://www.karlancer.com/projects/",
        "fee_note": "تسویه از طریق پلتفرم",
    },
    "parscoders": {
        "enabled": True,
        "label": "پارس‌کدرز",
        "kind": "parscoders",
        "base_url": "https://parscoders.com",
        "listing_url": "https://parscoders.com/project",
        "project_url_prefix": "https://parscoders.com/project/",
        "fee_note": "تسویه از طریق پلتفرم",
    },
}


def merged_sources(raw_sources: dict | None) -> dict:
    """ادغامِ تنظیماتِ کاربر با پیش‌فرض‌ها (تنظیماتِ کاربر مقدم است).

    دو قانون:
    - اگر اصلاً منبعی تعریف نشده (فایلِ تنظیمات خوانده نشده)، همه‌ی پیش‌فرض‌ها
      به کار می‌روند تا برنامه بی‌منبع نماند.
    - در غیر این صورت فقط فیلدهایِ خالیِ هر منبع از پیش‌فرض پُر می‌شوند و
      منبعِ تازه‌ای به کاربر تحمیل نمی‌شود.
    """
    raw = raw_sources or {}
    if not raw:
        return {key: dict(value) for key, value in DEFAULT_SOURCES.items()}

    merged: dict[str, dict] = {}
    for key, value in raw.items():
        item = dict(DEFAULT_SOURCES.get(key) or {})
        item.update(value or {})
        merged[key] = item
    return merged


def listing_url_for(key: str, scfg: dict | None) -> str:
    """نشانیِ فهرستِ یک منبع: از تنظیمات، وگرنه از پیش‌فرضِ داخل برنامه."""
    value = str((scfg or {}).get("listing_url") or "").strip()
    if value:
        return value
    return str(DEFAULT_SOURCES.get(key, {}).get("listing_url") or "").strip()
