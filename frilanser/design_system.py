"""سیستم طراحی (Design System) برای پیش‌نمایش‌های گرافیکی.

به‌جای اینکه هر دمو را دستی بنویسیم، خروجی از ترکیبِ منظمِ این سه ساخته می‌شود:

  سبک (Style)   → هویت بصری: شیشه‌ای، نئومورفیک، مینیمال، بروتالیست، لاکچری، …
  پالت (Palette) → رنگ‌ها و گرادینت‌ها
  فونت‌ها        → جفت‌فونت برای تیتر و متن (با fallback برای ویندوز)

هر سبک توکن‌های خودش را دارد (شعاع، سایه، حاشیه، افکت) و در قالب متغیرهای CSS
تزریق می‌شود؛ کامپوننت‌ها فقط توکن‌ها را مصرف می‌کنند. در پایان یک «بررسی کیفیت»
خروجی را از نظر کنتراست رنگ، ریسپانسیو، دسترس‌پذیری و منابع خارجی چک می‌کند.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# فونت‌ها — برای هر سیستم fallback گذاشته شده تا روی ویندوز هم درست نمایش داده شود
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FontPairing:
    key: str
    label: str
    heading: str
    body: str


FONTS: dict[str, FontPairing] = {
    "modern": FontPairing(
        "modern", "مدرن (بدون‌زواید)",
        '"Vazirmatn","IRANSans","Segoe UI",Tahoma,sans-serif',
        '"Vazirmatn","IRANSans","Segoe UI",Tahoma,sans-serif'),
    "friendly": FontPairing(
        "friendly", "صمیمی و گرد",
        '"Sahel","Shabnam","Vazirmatn",Tahoma,sans-serif',
        '"Sahel","Shabnam","Vazirmatn",Tahoma,sans-serif'),
    "classical": FontPairing(
        "classical", "کلاسیک (تیتر نستعلیق/عنوانی)",
        '"B Titr","Tanha","Vazirmatn",Tahoma,serif',
        '"B Nazanin","Vazirmatn",Tahoma,serif'),
    "tech": FontPairing(
        "tech", "تکنولوژی (یک‌دست)",
        '"Shabnam","Vazirmatn",Consolas,"Segoe UI",sans-serif',
        '"Shabnam","Vazirmatn","Segoe UI",Tahoma,sans-serif'),
    "elegant": FontPairing(
        "elegant", "لوکس (تیتر باریک)",
        '"B Nazanin","Vazirmatn",Georgia,serif',
        '"B Nazanin","Vazirmatn",Tahoma,serif'),
    "bold": FontPairing(
        "bold", "برجسته (هدرهای ضخیم)",
        '"B Titr","Vazirmatn",Impact,sans-serif',
        '"Vazirmatn","IRANSans",Tahoma,sans-serif'),
}


# --------------------------------------------------------------------------- #
# پالت‌های رنگی
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Palette:
    key: str
    label: str
    primary: str
    accent: str
    ink: str        # رنگ متن اصلی
    mut: str        # رنگ متن فرعی
    line: str       # خطوط و حاشیه‌ها
    bg: str         # پس‌زمینه
    surface: str    # پس‌زمینه‌ی کارت‌ها
    gradient: str


PALETTES: dict[str, Palette] = {
    "indigo": Palette("indigo", "نیلی/آبی", "#3b5bdb", "#22b8cf", "#161a2b", "#6b7280",
                      "#e6e9f2", "#f6f7fc", "#ffffff",
                      "linear-gradient(135deg,#2b3a67 0%,#3b5bdb 55%,#22b8cf 100%)"),
    "emerald": Palette("emerald", "سبز درمانی", "#0e9f6e", "#22b8cf", "#132a24", "#5f6f6a",
                       "#dceee7", "#f4fbf8", "#ffffff",
                       "linear-gradient(135deg,#0b6b4f 0%,#0e9f6e 55%,#22b8cf 100%)"),
    "medical": Palette("medical", "آبی پزشکی", "#1d4ed8", "#0ea5e9", "#111c3a", "#5b6b8c",
                       "#dde6f8", "#f5f8fe", "#ffffff",
                       "linear-gradient(135deg,#12306b 0%,#1d4ed8 55%,#0ea5e9 100%)"),
    "gold": Palette("gold", "طلایی لوکس", "#a16207", "#d97706", "#241a05", "#7c6a45",
                    "#f0e2c2", "#fdf9ef", "#ffffff",
                    "linear-gradient(135deg,#7c4a03 0%,#a16207 55%,#e0a53a 100%)"),
    "graphite": Palette("graphite", "گرافیت صنعتی", "#334155", "#f59e0b", "#111827", "#64748b",
                        "#dfe3ea", "#f4f5f7", "#ffffff",
                        "linear-gradient(135deg,#1f2937 0%,#334155 55%,#f59e0b 100%)"),
    "rose": Palette("rose", "صورتی/مرجانی", "#db2777", "#f59e0b", "#2a1020", "#7c5a6b",
                    "#f7e2ec", "#fef7fb", "#ffffff",
                    "linear-gradient(135deg,#9d174d 0%,#db2777 55%,#f59e0b 100%)"),
    "violet": Palette("violet", "بنفش خلاق", "#6d28d9", "#0ea5e9", "#1b1033", "#6f6791",
                      "#e7ddfb", "#faf7ff", "#ffffff",
                      "linear-gradient(135deg,#4c1d95 0%,#6d28d9 55%,#0ea5e9 100%)"),
    "midnight": Palette("midnight", "شبانه (تیره)", "#60a5fa", "#a78bfa", "#e8ecf7", "#98a5c4",
                        "#1f2a44", "#0b1120", "#141c2e",
                        "linear-gradient(135deg,#0b1120 0%,#1e3a8a 55%,#7c3aed 100%)"),
    "neon": Palette("neon", "نئون تکنولوژی", "#22d3ee", "#f472b6", "#e6faff", "#8fa6bd",
                    "#123243", "#071018", "#0c1a24",
                    "linear-gradient(135deg,#071018 0%,#0e7490 50%,#db2777 100%)"),
    "sand": Palette("sand", "خاکی/کاغذی", "#b45309", "#0f766e", "#2b2115", "#7a6a55",
                    "#e9dfcd", "#fbf7f0", "#ffffff",
                    "linear-gradient(135deg,#7c3f10 0%,#b45309 55%,#0f766e 100%)"),
    "ocean": Palette("ocean", "اقیانوسی عمیق", "#0ea5e9", "#14b8a6", "#0b2233", "#5d7f92",
                     "#d6ecf7", "#f2fbff", "#ffffff",
                     "linear-gradient(135deg,#075985 0%,#0ea5e9 55%,#14b8a6 100%)"),
    "crimson": Palette("crimson", "زرشکی/رستورانی", "#b91c1c", "#f59e0b", "#2b0f0f", "#7d5a5a",
                       "#f4dede", "#fef8f8", "#ffffff",
                       "linear-gradient(135deg,#7f1d1d 0%,#b91c1c 55%,#f59e0b 100%)"),
}


# --------------------------------------------------------------------------- #
# سبک‌ها (هویت بصری)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Style:
    key: str
    label: str
    description: str
    palette: str
    fonts: str
    radius: str
    shadow: str
    border: str
    effects: tuple[str, ...] = field(default_factory=tuple)   # glass | mesh | glow | noise | grid
    hero: str = "split"          # split | centered | image-left
    card: str = "soft"           # soft | glass | flat | outline | neumorph
    surface_alpha: str = "1"     # شفافیت سطح کارت‌ها (برای شیشه‌ای)


STYLES: dict[str, Style] = {
    "soft_saas": Style(
        "soft_saas", "SaaS مدرن", "گرد، سایه‌های نرم، گرادینت ملایم — مناسب استارتاپ و خدمات",
        "indigo", "modern", "18px", "0 8px 26px rgba(21,32,70,.08)", "1px solid var(--line)",
        ("mesh",), "split", "soft"),
    "glassmorphism": Style(
        "glassmorphism", "شیشه‌ای (Glassmorphism)", "سطوح نیمه‌شفاف با بلور پس‌زمینه و گرادینت پویا",
        "violet", "modern", "22px", "0 18px 50px rgba(16,24,64,.16)", "1px solid rgba(255,255,255,.35)",
        ("glass", "mesh"), "centered", "glass", "0.62"),
    "neumorphism": Style(
        "neumorphism", "نئومورفیک", "سایه‌های دوقلوی نرم، برجستگی ملایم، بدون خطوط تند",
        "indigo", "friendly", "26px", "10px 10px 24px #dfe3ee, -10px -10px 24px #ffffff",
        "1px solid rgba(255,255,255,.5)", (), "centered", "neumorph"),
    "minimal": Style(
        "minimal", "مینیمال", "فضای سفید زیاد، خطوط نازک، تمرکز روی محتوا",
        "graphite", "modern", "8px", "0 1px 2px rgba(16,24,40,.04)", "1px solid var(--line)",
        (), "centered", "flat"),
    "brutalist": Style(
        "brutalist", "بروتالیست", "حاشیه‌های ضخیم، گوشه‌های تیز، کنتراست بالا",
        "graphite", "bold", "0", "8px 8px 0 var(--p)", "3px solid var(--ink)",
        (), "split", "outline"),
    "dark_elegant": Style(
        "dark_elegant", "تاریکِ شیک", "پس‌زمینه تیره با درخشش ملایم و تیترهای باریک",
        "midnight", "elegant", "16px", "0 20px 60px rgba(0,0,0,.45)", "1px solid #1f2a44",
        ("glow",), "split", "soft"),
    "luxury_gold": Style(
        "luxury_gold", "لاکچری طلایی", "مشکی و طلا، تیترهای کلاسیک، مناسب طلا و جواهر/برند لوکس",
        "gold", "elegant", "6px", "0 16px 44px rgba(70,50,10,.28)", "1px solid #e6cf9d",
        ("glow",), "centered", "soft"),
    "neon_tech": Style(
        "neon_tech", "نئون تکنولوژی", "تیره با درخشش نئونی، مناسب محصولات فنی و داشبورد",
        "neon", "tech", "14px", "0 0 30px rgba(34,211,238,.22)", "1px solid #123243",
        ("glow", "grid"), "split", "outline"),
    "corporate": Style(
        "corporate", "شرکتی رسمی", "ساختار منظم و قابل اعتماد برای شرکت‌ها و سازمان‌ها",
        "medical", "modern", "10px", "0 6px 18px rgba(16,32,70,.07)", "1px solid var(--line)",
        (), "split", "soft"),
    "warm_editorial": Style(
        "warm_editorial", "گرم و روایی", "کاغذی، تیترهای کلاسیک، مناسب رستوران و محتوای فرهنگی",
        "sand", "classical", "12px", "0 10px 30px rgba(90,60,20,.12)", "1px solid #e6d9c2",
        (), "image-left", "flat"),
    "playful": Style(
        "playful", "پرانرژی و گرد", "رنگ‌های شاد، گوشه‌های خیلی گرد، مناسب آموزش و فروشگاه",
        "violet", "friendly", "28px", "0 14px 34px rgba(88,45,180,.16)", "1px solid var(--line)",
        ("mesh",), "centered", "soft"),
    "medical_clean": Style(
        "medical_clean", "درمانیِ پاک", "سفید و سبز/آبی، حس اعتماد و پاکیزگی",
        "emerald", "modern", "16px", "0 10px 28px rgba(11,80,60,.10)", "1px solid var(--line)",
        (), "split", "soft"),
    "ocean_trust": Style(
        "ocean_trust", "اعتمادِ اقیانوسی", "آبی عمیق با حس اطمینان، مناسب مالی و املاک",
        "ocean", "modern", "14px", "0 12px 32px rgba(7,89,133,.14)", "1px solid var(--line)",
        ("mesh",), "split", "soft"),
    "rose_shop": Style(
        "rose_shop", "فروشگاهیِ گرم", "صورتی و نارنجی، مناسب فروشگاه و محصولات مصرفی",
        "rose", "friendly", "20px", "0 14px 34px rgba(157,23,77,.14)", "1px solid var(--line)",
        ("mesh",), "split", "soft"),
}

# کلیدواژه‌های آگهی → سبک پیشنهادی (مثل انتخاب دستیِ طراح)
KEYWORD_STYLES: list[tuple[str, str]] = [
    (r"طلا|جواهر|زرگر|لوکس|لاکچری|تشریفات", "luxury_gold"),
    (r"تجهیزات پزشکی|تجهیزات آزمایشگاه|شرکت|سازمان|صنعت|کارخانه|تولیدی|صادرات", "corporate"),
    (r"کلینیک|درمان|دندان|مطب|بیمارستان|داروخانه|آزمایشگاه|زیبایی", "medical_clean"),
    (r"رستوران|کافه|فست ?فود|غذا|منو|شیرینی", "warm_editorial"),
    (r"فروشگاه|shop|محصول|فروش آنلاین|دیجی ?کالا", "rose_shop"),
    (r"املاک|ملک|بیمه|مالی|بانک|سرمایه", "ocean_trust"),
    (r"آموزش|دوره|مدرسه|کودک|بازی|سرگرمی", "playful"),
    (r"هوش مصنوعی|داده|داشبورد|api|ربات|اتوماسیون|بلاکچین", "neon_tech"),
    (r"استارتاپ|اپلیکیشن|نرم ?افزار|سامانه|پلتفرم", "soft_saas"),
    (r"شیشه|مدرن|مینیمال|طراحی خاص|glass", "glassmorphism"),
]

# آرکتایپ → سبک پیش‌فرض (وقتی کلیدواژه‌ای پیدا نشود)
ARCHETYPE_STYLES = {
    "clinic": "medical_clean",
    "med_equipment": "corporate",
    "industrial": "brutalist",
    "gold_shop": "luxury_gold",
    "shop": "rose_shop",
    "restaurant": "warm_editorial",
    "realestate": "ocean_trust",
    "education": "playful",
    "corporate": "corporate",
}


def pick_style(project=None, archetype: str = "corporate", override: str = "") -> Style:
    """انتخاب سبک: اول دستی، بعد کلیدواژه‌های آگهی، بعد آرکتایپ."""
    if override and override in STYLES:
        return STYLES[override]
    if override and override in PALETTES:
        for st in STYLES.values():
            if st.palette == override:
                return st
    if project is not None:
        hay = f"{project.title} {project.description}"
        for pattern, style_key in KEYWORD_STYLES:
            if re.search(pattern, hay, re.I):
                return STYLES[style_key]
    return STYLES.get(ARCHETYPE_STYLES.get(archetype, "corporate"), STYLES["corporate"])


def palette_of(style: Style) -> Palette:
    p = PALETTES[style.palette]
    if contrast_ratio(p.mut, p.surface) < 3.5:  # متن فرعی را خودکار خواناتر می‌کنیم
        p = Palette(p.key, p.label, p.primary, p.accent, p.ink, _darken(p.mut, 0.18),
                    p.line, p.bg, p.surface, p.gradient)
    return p


def _darken(color: str, amount: float) -> str:
    r, g, b = _hex_to_rgb(color)
    f = 1 - amount
    return "#%02x%02x%02x" % (int(r * f), int(g * f), int(b * f))


def fonts_of(style: Style) -> FontPairing:
    return FONTS.get(style.fonts, FONTS["modern"])


# --------------------------------------------------------------------------- #
# تولید CSS متناسب با سبک
# --------------------------------------------------------------------------- #
def css_tokens(style: Style) -> str:
    p = palette_of(style)
    f = fonts_of(style)
    return f"""
:root{{
--p:{p.primary};--a:{p.accent};--ink:{p.ink};--mut:{p.mut};--line:{p.line};
--bg:{p.bg};--surface:{p.surface};--grad:{p.gradient};
--r:{style.radius};--shadow:{style.shadow};--stroke:{style.border};
--alpha:{style.surface_alpha};
--font-h:{f.heading};--font-b:{f.body};
}}
"""


def on_primary(primary: str) -> str:
    """رنگ متن روی دکمه: از بین سفید/تیره، هرکدام کنتراست بهتری دارد."""
    return max(("#ffffff", "#0b1120", "#101828"), key=lambda c: contrast_ratio(c, primary))


def css_style(style: Style) -> str:
    p = palette_of(style)
    # اگر کنتراست متن فرعی کم باشد، آن را کمی تیره می‌کنیم
    parts: list[str] = ["body{font-family:var(--font-b);background:var(--bg);color:var(--ink)}",
                        f".btn{{color:{on_primary(p.primary)}}}",
                        f".btn.alt{{color:{on_primary(p.accent)}}}",
                        "h1,h2,h3,.t,.stat .v,.kpi .v{font-family:var(--font-h)}"]

    if "mesh" in style.effects:
        parts.append(
            "body:before{content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;"
            f"background:radial-gradient(900px 500px at 12% -5%,{p.primary}22,transparent 60%),"
            f"radial-gradient(800px 480px at 92% 8%,{p.accent}1f,transparent 62%),"
            "radial-gradient(700px 420px at 50% 110%,#00000012,transparent 60%)}"
        )
    if "grid" in style.effects:
        parts.append(
            "body:after{content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.35;"
            "background-image:linear-gradient(#22d3ee0f 1px,transparent 1px),"
            "linear-gradient(90deg,#22d3ee0f 1px,transparent 1px);background-size:44px 44px}"
        )
    if "noise" in style.effects:
        parts.append("body{background-blend-mode:multiply}")

    card_rules = {
        "glass": ("background:rgba(255,255,255,var(--alpha));backdrop-filter:blur(14px) saturate(140%);"
                  "-webkit-backdrop-filter:blur(14px) saturate(140%);border:var(--stroke)"),
        "neumorph": ("background:var(--surface);border:1px solid rgba(255,255,255,.6)"),
        "flat": ("background:var(--surface);border:0"),
        "outline": ("background:transparent;border:var(--stroke)"),
        "soft": ("background:var(--surface);border:var(--stroke)"),
    }[style.card]
    parts.append(f".card,.card2,.prod,.quote,.kpi,.mockwin,.stat{{{card_rules}}}")

    if style.card == "glass":
        parts.append(".sect.alt{background:rgba(255,255,255,.06)}"
                     ".mh{background:rgba(255,255,255,.55);backdrop-filter:blur(10px)}")
    if style.card == "neumorph":
        parts.append(".card,.card2,.prod,.quote{box-shadow:var(--shadow)}")
    else:
        parts.append(".card,.card2,.prod,.quote{box-shadow:var(--shadow)}")

    if "glow" in style.effects:
        parts.append(f".btn,.kpi .v{{box-shadow:0 0 26px {p.primary}55}}"
                     ".mockwin{box-shadow:0 24px 70px rgba(0,0,0,.5)}")
    parts.append(f".hero{{background:var(--grad)}}")
    parts.append("a:focus-visible,button:focus-visible,input:focus-visible,"
                 "select:focus-visible{outline:3px solid var(--a);outline-offset:2px}")
    parts.append("@media (prefers-reduced-motion: reduce){*{animation:none!important;"
                 "transition:none!important}}")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# بررسی کیفیت خروجی (کنتراست، ریسپانسیو، دسترس‌پذیری، منابع خارجی)
# --------------------------------------------------------------------------- #
def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    try:
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    except ValueError:
        return (0, 0, 0)


def _luminance(color: str) -> float:
    r, g, b = _hex_to_rgb(color)

    def ch(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def check_design(html: str, style: Style, client_version: bool = False) -> tuple[list[str], list[str]]:
    """بررسی خروجی؛ برمی‌گرداند (خطاها، هشدارها)."""
    errors: list[str] = []
    warnings: list[str] = []
    p = palette_of(style)

    # کنتراست متن با پس‌زمینه
    ratio_body = contrast_ratio(p.ink, p.bg)
    if ratio_body < 4.5:
        errors.append(f"کنتراست متن با پس‌زمینه کم است ({ratio_body}:1؛ حداقل ۴.۵:۱)")
    ratio_btn = contrast_ratio(on_primary(p.primary), p.primary)
    if ratio_btn < 3.0:
        errors.append(f"کنتراست متنِ دکمه روی رنگ اصلی کم است ({ratio_btn}:1)")
    ratio_mut = contrast_ratio(p.mut, p.surface)
    if ratio_mut < 3.5:
        warnings.append(f"کنتراست متنِ فرعی کم است ({ratio_mut}:1)")

    # ریسپانسیو
    if 'name="viewport"' not in html:
        errors.append("تگ viewport ندارد (نمایش موبایل درست نمی‌شود)")
    if "@media" not in html:
        errors.append("هیچ قانون رسپانسیو (@media) ندارد")

    # دسترس‌پذیری پایه
    if "lang=\"fa\"" not in html or 'dir="rtl"' not in html:
        errors.append("زبان/جهت صفحه (lang/dir) تنظیم نشده")
    if "focus-visible" not in html:
        warnings.append("حالت فوکس کیبورد تعریف نشده")
    if "prefers-reduced-motion" not in html:
        warnings.append("به تنظیم «کاهش انیمیشن» کاربر احترام گذاشته نشده")

    # منابع خارجی (دمو باید آفلاین و تک‌فایل باشد)
    external = re.findall(r'(?:src|href)\s*=\s*"(https?://[^"]+)"', html)
    if external and client_version:
        errors.append(f"نسخه‌ی کارفرما به اینترنت وابسته است: {external[:2]}")
    elif external:
        warnings.append(f"{len(external)} منبع خارجی در صفحه هست (فقط در نسخه‌ی داخلی مجاز است)")

    # قفلِ استفاده
    for token, msg in (('id="wm"', "واترمارک"), ('id="guard"', "لایه‌ی مسدودکننده"),
                       ("disabled=true", "غیرفعال‌سازی فرم‌ها")):
        if token not in html:
            errors.append(f"{msg} در خروجی نیست")
    if "noindex" not in html:
        warnings.append("برچسب noindex ندارد")

    return errors, warnings


def list_styles() -> list[tuple[str, str, str, str]]:
    return [(s.key, s.label, s.description, palette_of(s).label) for s in STYLES.values()]
