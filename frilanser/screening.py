"""غربالگری پروژه‌ها: آیا این پروژه در آرنا (عامل هوش مصنوعیِ سندباکسی) قابل اجرا هست؟

خروجی برای هر پروژه:
  - دسته‌بندی
  - امتیاز اجراپذیری (۰ تا ۱۰۰) همراه با دلایل فارسی
  - برآورد زمان (ساعت) و زمان‌بندی تحویل (روز)
  - موانع / ریسک‌ها / کارهایی که فقط خودِ شما باید انجام دهید
  - خروجی‌های قابل تحویل
"""

from __future__ import annotations

import math
import re

from .config import Config
from .models import Project
from .normalize import (
    clean_text,
    extract_bullets,
    parse_language_count,
    parse_page_count,
)

# ============================================================
#  دسته‌بندی پروژه‌ها
#  fit: yes (آرنا می‌تواند کامل تحویل دهد) | partial (بخشی) | no (خیر)
# ============================================================

CATEGORIES: dict[str, dict] = {
    # ---------- کاملاً مناسب آرنا ----------
    "data_pipeline": {
        "label": "استخراج و پردازش داده",
        "fit": "yes", "hours": 10, "priority": 0,
        "patterns": [r"استخراج", r"پردازش داده", r"\bpdf\b", r"epub", r"\bjson\b", r"\bcsv\b",
                     r"اکسل", r"excel", r"ساختاریافته", r"کتاب", r"متن کامل", r"فرمول",
                     r"داده‌های", r"\betl\b", r"تبدیل فرمت", r"پاکسازی داده"],
        "tech": ["Python", "pdfplumber / PyMuPDF", "pandas", "خروجی JSON/CSV"],
        "deliverables": ["اسکریپت پایتون با رابط خط فرمان (CLI)",
                          "خروجی ساختاریافته (JSON/CSV) شامل متن، جداول و تصاویر",
                          "اجرای نمونه روی یک فایل واقعی + گزارش دقت",
                          "مستندات کوتاهِ اجرا و نصب"],
    },
    "automation": {
        "label": "اسکریپت و اتوماسیون",
        "fit": "yes", "hours": 8, "priority": 0,
        "patterns": [r"اسکریپت", r"اتوماتیک", r"خودکار", r"اتوماسیون", r"کرال", r"خزش",
                     r"scaping", r"scraping", r"جمع‌آوری اطلاعات از سایت", r"ربات .*وب",
                     r"برنامه‌نویسی پایتون", r"پایتون", r"python", r"زمان‌بندی"],
        "tech": ["Python", "requests / Playwright", "زمان‌بند (cron)", "خروجی فایل/پایگاه داده"],
        "deliverables": ["اسکریپت اجرایی + فایل پیکربندی",
                          "گزارش اجرا و لاگ خطاها",
                          "راهنمای اجرا و زمان‌بندی"],
    },
    "bot": {
        "label": "ربات / بات",
        "fit": "yes", "hours": 12, "priority": 0,
        "patterns": [r"ربات تلگرام", r"بات تلگرام", r"ربات ایتا", r"ربات بله", r"ساخت ربات",
                     r"بات", r"ربات", r"chatbot", r"چت‌بات", r"دستیار هوشمند", r"webhook"],
        "tech": ["Python", "python-telegram-bot / API مستقیم", "SQLite", "Docker"],
        "deliverables": ["سورس کامل ربات + فایل راه‌اندازی",
                          "پنل مدیریت ساده (در صورت نیاز)",
                          "مستندات نصب روی سرور"],
    },
    "ai_app": {
        "label": "اپلیکیشن هوش مصنوعی",
        "fit": "yes", "hours": 16, "priority": 0,
        "patterns": [r"هوش مصنوعی", r"\bai\b", r"مدل زبانی", r"llm", r"embedding", r"\brag\b",
                     r"agent", r"عامل هوشمند", r"chatgpt", r"claude", r"تحلیل هوشمند"],
        "tech": ["Python", "API مدل زبانی", "Embedding / پایگاه برداری", "رابط وب"],
        "deliverables": ["سورس برنامه + رابط کاربری وب",
                          "مستندات prompt/تنظیمات",
                          "نمونه اجرا روی داده واقعی"],
    },
    "landing": {
        "label": "لندینگ‌پیج / صفحه معرفی",
        "fit": "yes", "hours": 6, "priority": 0,
        "patterns": [r"لندینگ", r"landing", r"صفحه فرود", r"صفحه معرفی محصول"],
        "tech": ["HTML/CSS/JS", "طراحی واکنش‌گرا"],
        "deliverables": ["فایل‌های آماده‌ی انتشار (Static)", "نسخه دموی آنلاین", "فرم جذب سرنخ"],
    },
    "dashboard": {
        "label": "داشبورد و گزارش‌ساز",
        "fit": "yes", "hours": 12, "priority": 0,
        "patterns": [r"داشبورد", r"dashboard", r"گزارش‌ساز", r"گزارش گیری", r"نمودار",
                     r"panel مدیریت", r"پنل آماری", r"گزارش ماهانه", r"kpi"],
        "tech": ["Python / Flask", "Chart.js", "SQLite", "خروجی Excel/PDF"],
        "deliverables": ["داشبورد وب با فیلتر و جستجو", "خروجی گزارش", "مستندات"],
    },
    "web_app": {
        "label": "وب‌سایت / وب‌اپلیکیشن",
        "fit": "yes", "hours": 12, "priority": 0,
        "patterns": [r"وب\s?سایت", r"وبسایت", r"طراحی سایت", r"سایت شرکتی", r"سایت فروشگاهی",
                     r"فروشگاه اینترنتی", r"وب\s?اپ", r"web ?app", r"پورتال", r"سامانه",
                     r"پنل کاربری", r"پروفایل کاربر", r"رزرو نوبت", r"سیستم مدیریت محتوا",
                     r"واکنش‌گرا", r"responsive", r"سایت", r"صفحه اصلی"],
        "tech": ["HTML/CSS/JS", "Flask / FastAPI", "SQLite", "طراحی واکنش‌گرا"],
        "deliverables": ["سورس کامل + فایل‌های آماده‌ی انتشار",
                          "نسخه دموی آنلاین برای بازدید کارفرما",
                          "راهنمای مدیریت محتوا", "چک‌لیست سئو پایه"],
    },
    "chrome_extension": {
        "label": "افزونه مرورگر",
        "fit": "partial", "hours": 10, "priority": 0,
        "patterns": [r"افزونه مرورگر", r"chrome extension", r"اکستنشن", r"افزونه کروم"],
        "tech": ["JavaScript", "Manifest V3"],
        "deliverables": ["سورس افزونه + فایل نصب", "راهنمای نصب"],
    },
    "plugin_cms": {
        "label": "افزونه / قالب وردپرس",
        "fit": "partial", "hours": 12, "priority": 0,
        "patterns": [r"افزونه وردپرس", r"پلاگین", r"قالب وردپرس", r"ووکامرس", r"المنتور",
                     r"شورت\s?کد", r"shortcode", r"woocommerce", r"elementor"],
        "tech": ["PHP", "WordPress", "JavaScript"],
        "deliverables": ["کد افزونه/قالب به‌صورت فایل ZIP قابل نصب", "مستندات نصب و تنظیمات"],
    },
    "mobile_app": {
        "label": "اپلیکیشن موبایل",
        "fit": "partial", "hours": 24, "priority": 0,
        "patterns": [r"اپلیکیشن (?:موبایل|اندروید|ios)", r"اندروید", r"\bios\b", r"flutter",
                     r"react native", r"ساخت اپ", r"اپ فروشگاهی", r"نرم‌افزار ویندوز"],
        "tech": ["React / PWA", "در صورت نیاز: Flutter"],
        "deliverables": ["نسخه وب/PWA قابل اجرا روی موبایل",
                          "در صورت توافق: سورس Flutter (ساخت نهایی با اکانت شما)"],
    },
    # ---------- بخشی قابل اجرا ----------
    "content": {
        "label": "تولید محتوا / ترجمه",
        "fit": "partial", "hours": 8, "priority": 0,
        "patterns": [r"تولید محتوا", r"مقاله", r"رپورتاژ", r"ترجمه", r"تایپ", r"واژه",
                     r"کپی‌رایت", r"محتوای سایت", r"blog", r"وبلاگ"],
        "tech": ["مدل زبانی + ویرایش انسانی"],
        "deliverables": ["متن‌ها در فایل Word/Google Docs", "گزارش اصالت و منابع", "یک دور بازنگری"],
    },
    "data_entry": {
        "label": "ورود و به‌روزرسانی داده",
        "fit": "partial", "hours": 12, "priority": 0,
        "patterns": [r"ورود اطلاعات", r"دیتا اینتری", r"data entry", r"به‌روزرسانی اطلاعات",
                     r"ثبت داده", r"راستی‌آزمایی", r"جستجو در وب", r"بانک اطلاعاتی"],
        "tech": ["Python + جستجوی خودکار", "بررسی انسانی موارد مشکوک"],
        "deliverables": ["فایل نهایی (اکسل/CSV)", "گزارش موارد تاییدنشده", "اسکریپت جمع‌آوری"],
    },
    # ---------- مناسب نیست ----------
    "seo": {
        "label": "سئو و بهینه‌سازی مستمر",
        "fit": "no", "hours": 30, "priority": 0.5,
        "patterns": [r"\bسئو\b", r"seo", r"بک‌لینک", r"لینک‌سازی", r"رتبه گوگل",
                     r"search console", r"کیورد", r"keyword research", r"افزایش ورودی ارگانیک"],
        "tech": [], "deliverables": [],
    },
    "design": {
        "label": "طراحی گرافیک / لوگو / کاتالوگ",
        "fit": "no", "hours": 8, "priority": 0.5,
        "patterns": [r"طراحی لوگو", r"لوگو", r"طراحی گرافیک", r"کاتالوگ", r"این‌دیزاین",
                     r"indesign", r"فتوشاپ", r"photoshop", r"ایلاستریتور", r"illustrator",
                     r"کورل", r"corel", r"طراحی کارت ویزیت", r"بنر", r"تراکت", r"پوستر",
                     r"اینفوگرافیک", r"رابط کاربری.*طراحی", r"ui design"],
        "tech": [], "deliverables": [],
    },
    "three_d": {
        "label": "مدلسازی سه‌بعدی و رندرینگ",
        "fit": "no", "hours": 16, "priority": 0.5,
        "patterns": [r"رندر", r"سه بعدی", r"3d", r"مدلسازی", r"معماری داخلی", r"\bvr\b",
                     r"تردی‌مکس", r"بلندر", r"blender", r"اتوکد", r"autocad", r"نقشه‌کشی"],
        "tech": [], "deliverables": [],
    },
    "video": {
        "label": "تدوین / موشن‌گرافی / صدا",
        "fit": "no", "hours": 16, "priority": 0.5,
        "patterns": [r"تدوین", r"موشن", r"انیمیشن", r"تیزر", r"دوبله", r"گویندگی", r"آهنگسازی",
                     r"ویرایش ویدیو", r"صداگذاری"],
        "tech": [], "deliverables": [],
    },
    "teaching": {
        "label": "آموزش / تدریس / مشاوره",
        "fit": "no", "hours": 20, "priority": 0.5,
        "patterns": [r"مدرس", r"تدریس", r"آموزش (?:بد|ده|می)", r"جلسات آموزشی", r"منتور",
                     r"مشاوره", r"کلاس", r"کارگاه", r"یاد بگیرم", r"یاد بده"],
        "tech": [], "deliverables": [],
    },
    "ops_admin": {
        "label": "ادمین / پشتیبانی مستمر (کار انسانی)",
        "fit": "no", "hours": 20, "priority": 0.5,
        "patterns": [r"ادمین (?:تلگرام|اینستاگرام|سایت|پاسخگو|شبکه)", r"پاسخگویی", r"شیفت",
                     r"استخدام", r"همکاری مستمر", r"پشتیبانی مشتریان", r"دستیار مجازی",
                     r"مدیریت شبکه‌های اجتماعی", r"استخدام بازیگر"],
        "tech": [], "deliverables": [],
    },
    "hardware": {
        "label": "سخت‌افزار / تأسیسات / اجرای میدانی",
        "fit": "no", "hours": 30, "priority": 0.5,
        "patterns": [r"تأسیسات", r"تاسیسات", r"موتورخانه", r"سخت‌افزار", r"مدار (?:چاپی|الکتریکی)",
                     r"plc", r"arduino", r"آردوینو", r"رزبری", r"raspberry", r"دوربین مداربسته",
                     r"آلارم", r"اثر ?انگشت", r"\bdvr\b", r"حضوری", r"نصب و راه‌اندازی تجهیز",
                     r"گرمایش از کف", r"استخر", r"برق ساختمان"],
        "tech": [], "deliverables": [],
    },
    "trading": {
        "label": "ربات معاملاتی / ترید",
        "fit": "no", "hours": 20, "priority": 0.5,
        "patterns": [r"بورس", r"سهام", r"ترید", r"کریپتو", r"ارز دیجیتال", r"صرافی",
                     r"binance", r"kucoin", r"bybit", r"کارگزاری", r"سرخطی", r"بک‌تست",
                     r"بازدهی", r"سود روزانه", r"معاملات", r"رمزارز", r"رمز ارز",
                     r"کیف پول", r"wallet", r"فارکس", r"forex"],
        "tech": [], "deliverables": [],
    },
    "other": {
        "label": "سایر / نامشخص",
        "fit": "partial", "hours": 12, "priority": 0,
        "patterns": [], "tech": [], "deliverables": [],
    },
}

# ============================================================
#  نشانه‌های ریسک و موانع
# ============================================================

RESULT_CONTINGENT = [
    r"پرداخت .{0,40}مشروط", r"مشروط به (?:نتیجه|بازدهی|سود|تست|آزمون)",
    r"بازدهی", r"سود (?:روزانه|ماهانه|تضمینی)", r"درصد سود", r"تضمین سود",
    r"در صورت (?:رضایت کامل|فروش|نتیجه)", r"پرداخت پس از فروش",
]

HUMAN_OPERATION = [
    r"تلفن روابط عمومی", r"تماس تلفنی با", r"زنگ بزنید", r"حضور در محل", r"مراجعه حضوری",
    r"پاسخگویی به مشتریان", r"شیفت", r"به‌صورت روزانه .{0,20}پاسخ", r"ادمین",
    r"پشتیبانی (?:ماهانه|مستمر|\d+ ماهه)", r"\d+\s*ماه پشتیبانی",
]

LICENSED_SOFTWARE = [
    r"این‌دیزاین", r"indesign", r"اتوکد", r"autocad", r"تردی‌مکس", r"3ds ?max",
    r"فتوشاپ", r"photoshop", r"ایلاستریتور", r"illustrator", r"کورل", r"corel",
    r"\bmatlab\b", r"متلب", r"لایسنس",
]

ACCESS_NEEDED = [
    r"سایت (?:موجود|فعلی|من)", r"(?:^|\s)سایتم(?:\s|$|[،.؟])", r"از قبل آماده", r"از قبل ساخته شده",
    r"(?:سایت|وب\s?سایت|اپلیکیشن|فروشگاه)[^.\n]{0,40}(?:موجود|فعلی|از قبل)",
    r"ارتقا(?:ی|ء)? سایت", r"تکمیل (?:و آماده‌سازی )?(?:یک )?(?:وب|سایت|اپ)",
    r"کد فعلی", r"مخزن", r"repository", r"github", r"supabase",
    r"پیش‌تر[^\n]{0,60}(?:توسعه|انجام شده|ساخته شده)", r"مجری قبلی",
    r"ادامه‌ی? (?:توسعه|کار|پروژه)", r"توقف همکاری",
    r"دسترسی (?:به|های)?\s*(?:سرور|هاست|پنل|سایت|اکانت|api)",
    r"هاست", r"دامنه", r"cpanel", r"پنل پیامکی دارم", r"اکانت", r"\bapi key\b", r"کلید api",
    r"سرور ویندوز", r"روی سرور", r"بدون تبدیل پروژه به ساخت",
]

PHASED_SCOPE = [r"فاز (?:اول|دوم|بعدی)", r"در فاز بعد", r"در آینده", r"بعداً اضافه می‌شود"]

CMS_DELIVERY = [r"وردپرس", r"wordpress", r"ووکامرس", r"woocommerce", r"المنتور", r"elementor"]

ENTITY_COUNT = re.compile(
    r"(\d+)\s*(کتاب|فایل|مورد|صفحه|محصول|مقاله|آگهی|رکورد|سطر|کاربر|زبان|api)", re.IGNORECASE
)


# ============================================================
#  توابع اصلی
# ============================================================

def classify(project: Project) -> tuple[str, dict]:
    """دسته‌بندی پروژه بر اساس عنوان، توضیحات و مهارت‌ها."""
    text = clean_text(f"{project.title} {project.title} {project.description}").lower()
    skills = " ".join(project.skills).lower()
    haystack = f"{text} {skills}"

    best_key, best_score = "other", 0.0
    for key, rule in CATEGORIES.items():
        if not rule["patterns"]:
            continue
        hits = 0
        for pat in rule["patterns"]:
            if re.search(pat, haystack, re.IGNORECASE):
                hits += 1
        if hits == 0:
            continue
        score = hits + rule.get("priority", 0.0)
        # اگر در عنوان هم آمده باشد وزن بیشتر
        if any(re.search(pat, project.title, re.IGNORECASE) for pat in rule["patterns"]):
            score += 1.5
        if score > best_score:
            best_key, best_score = key, score
    return best_key, CATEGORIES[best_key]


def _hit(text: str, patterns: list[str]) -> list[str]:
    found = []
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            found.append(m.group(0))
    return found


def estimate_hours(project: Project, category: str) -> tuple[float, list[str]]:
    """برآورد زمان اجرا بر اساس دسته، حجم توضیحات، تعداد آیتم‌ها و پیچیدگی."""
    rule = CATEGORIES[category]
    hours = float(rule["hours"])
    notes: list[str] = [f"زمان پایه برای «{rule['label']}»: {hours:g} ساعت"]

    desc_len = len(project.description or "")
    if desc_len:
        add = min(6.0, desc_len / 400)
        hours += add
        notes.append(f"حجم توضیحات ({desc_len} کاراکتر): {add:.1f}+ ساعت")

    bullets = extract_bullets(project.description or "")
    if bullets:
        add = min(8.0, len(bullets) * 0.5)
        hours += add
        notes.append(f"{len(bullets)} مورد نیازمندی فهرست‌شده: {add:.1f}+ ساعت")

    pages = parse_page_count(f"{project.title} {project.description}")
    if pages and pages > 5:
        add = min(10.0, pages * 0.06)
        hours += add
        notes.append(f"گستره‌ی حدود {pages} صفحه: {add:.1f}+ ساعت")

    langs = parse_language_count(f"{project.title} {project.description}")
    if langs > 1:
        add = 2.0 * (langs - 1)
        hours += add
        notes.append(f"چندزبانه ({langs} زبان): {add:.1f}+ ساعت")

    counts = ENTITY_COUNT.findall(project.description or "")
    if counts:
        biggest = max(int(n) for n, _ in counts)
        unit = [u for n, u in counts if int(n) == biggest][0]
        add = min(6.0, math.log10(max(biggest, 2)) * 1.5)
        hours += add
        notes.append(f"حجم داده/محتوا ({biggest} {unit}): {add:.1f}+ ساعت")

    # فهرست‌های کاما-جدا (مثل «گالری تصویر، مقایسه محصول، درگاه پرداخت، …»)
    commas = len(re.findall(r"[،,;]", project.description or ""))
    if commas >= 8:
        add = min(8.0, commas * 0.25)
        hours += add
        notes.append(f"فهرست بلندِ امکانات ({commas} مورد تفکیک‌شده): {add:.1f}+ ساعت")

    return round(hours, 1), notes


def screen(project: Project, cfg: Config) -> dict:
    """تحلیل یک پروژه و تولید نتیجه‌ی غربالگری."""
    text = clean_text(f"{project.title}\n{project.description}")
    haystack = text + " " + " ".join(project.skills)
    sc = cfg.screening

    category, rule = classify(project)
    hours, hour_notes = estimate_hours(project, category)

    fit = rule["fit"]
    score = {"yes": 85, "partial": 55, "no": 15}[fit]
    reasons: list[dict] = []

    def add(code: str, text_: str, impact: int):
        nonlocal score
        score += impact
        reasons.append({"code": code, "text": text_, "impact": impact})

    fit_label = {"yes": "کاملاً مناسب", "partial": "تا حدی", "no": "مناسب نیست"}[fit]
    reasons.append({
        "code": "fit",
        "text": f"دسته‌بندی: {rule['label']} — قابلیت اجرا در آرنا: {fit_label}",
        "impact": 0,
    })

    blockers: list[str] = []
    needs_you: list[dict] = []
    risks: list[str] = []

    # ---------- موانع سخت ----------
    contingent = _hit(haystack, RESULT_CONTINGENT)
    if contingent:
        add("result_contingent",
            f"پرداخت/پذیرش مشروط به نتیجه است ({'، '.join(contingent[:2])}) — ریسک بالا",
            -int(sc.get("penalty_result_contingent", 25)))
        blockers.append("پرداخت مشروط به نتیجه/بازدهی")
        risks.append("پرداخت مشروط: امکان عدم دریافت مبلغ با وجود انجام کار")

    human_ops = _hit(haystack, HUMAN_OPERATION)
    if human_ops:
        add("human_operation",
            f"نیاز به حضور/عملیات انسانی مستمر ({'، '.join(human_ops[:2])})",
            -int(sc.get("penalty_human_operation", 20)))
        blockers.append("نیاز به نیروی انسانی مستمر")
        risks.append("بخشی از کار توسط عامل هوش مصنوعی قابل انجام نیست")

    licensed = _hit(haystack, LICENSED_SOFTWARE)
    if licensed:
        add("licensed_software",
            f"نیاز به نرم‌افزار دارای لایسنس/تخصصی ({'، '.join(licensed[:2])})",
            -int(sc.get("penalty_licensed_software", 10)))
        blockers.append("وابسته به نرم‌افزار لایسنس‌دار")
        risks.append("ابزار مورد نیاز کارفرما در سندباکس آرنا در دسترس نیست")

    access = _hit(haystack, ACCESS_NEEDED)
    if access:
        add("needs_access",
            f"برای اجرا به دسترسی/اطلاعات کارفرما نیاز است ({'، '.join(access[:2])})",
            -int(sc.get("penalty_needs_access", 10)))
        needs_you.append({
            "kind": "provide_access",
            "text": "دسترسی‌ها/اطلاعات مورد نیاز را از کارفرما بگیرید "
                    f"({', '.join(access[:3])}) و در اختیار آرنا قرار دهید.",
        })
        risks.append("بدون دسترسی، پیشنهاد فقط به‌صورت «تحویل کد + راهنما» قابل اجرا است")

    # ---------- شکل تحویل ----------
    if fit == "yes" and _hit(haystack, CMS_DELIVERY) and category in ("web_app", "plugin_cms", "landing"):
        needs_you.append({
            "kind": "delivery_format",
            "text": "کارفرما وردپرس/ووکامرس خواسته است. قبل از ثبت پیشنهاد مشخص کنید: "
                    "تحویل به‌صورت «سایت سبک و سریع با پنل مدیریت اختصاصی» "
                    "یا «قالب/افزونه وردپرس» (این تصمیم را شما با کارفرما نهایی می‌کنید).",
        })

    # ---------- رقابت ----------
    bids = project.bids
    if bids is not None:
        if bids >= int(sc.get("max_bids_penalty_at", 35)):
            add("bids", f"رقابت بسیار بالا ({bids} پیشنهاد)", -int(sc.get("penalty_max_bids", 12)))
        elif bids >= int(sc.get("high_bids_penalty_at", 20)):
            add("bids", f"رقابت بالا ({bids} پیشنهاد)", -int(sc.get("penalty_high_bids", 8)))
        elif bids <= 8:
            add("bids", f"رقابت کم ({bids} پیشنهاد) — شانس خوب", int(sc.get("bonus_low_competition", 4)))
        else:
            add("bids", f"رقابت متوسط ({bids} پیشنهاد)", 0)

    # ---------- بودجه ----------
    if project.budget_toman:
        add("budget", f"بودجه اعلام‌شده: {project.budget_toman:,} تومان", 0)
    else:
        add("budget", "بودجه اعلام نشده (توافقی)", -int(sc.get("penalty_no_budget", 5)))
        risks.append("مبلغ نهایی باید مذاکره شود")

    # ---------- وضوح ----------
    desc_len = len(clean_text(project.description or ""))
    if desc_len < 80:
        add("vague", f"توضیحات پروژه بسیار کوتاه و مبهم است ({desc_len} کاراکتر) — "
                     f"احتمال تغییر محدوده زیاد", -20)
        risks.append("ابهام زیاد در نیازمندی‌ها؛ قبل از قیمت قطعی باید توضیح بیشتری گرفت")
    elif desc_len < int(sc.get("min_description_chars", 150)):
        add("vague", f"توضیحات پروژه کوتاه است ({desc_len} کاراکتر) — بخشی از محدوده نامشخص است",
            -10)
        risks.append("ابهام در نیازمندی‌ها؛ قیمت‌گذاری قطعی بعد از یک جلسه‌ی توضیح")

    phased = _hit(haystack, PHASED_SCOPE)
    if phased:
        add("phased", "پروژه چندفازی تعریف شده و محدوده‌ی فاز اول دقیق مشخص نیست",
            -8)
        risks.append("فازبندی پروژه نامشخص است؛ پیشنهاد باید فقط روی یک فاز بسته شود")

    # ---------- تناسب بودجه با برآورد ----------
    if fit != "no":
        from .pricing import quick_price  # import محلی برای جلوگیری از وابستگی چرخه‌ای
        estimate = quick_price(cfg, hours, category)
        if project.budget_toman:
            ratio = project.budget_toman / estimate
            if ratio < 0.5:
                add("budget_fit",
                    f"بودجه ({project.budget_toman:,} تومان) کمتر از نصفِ برآورد ماست "
                    f"({estimate:,} تومان)", -25)
                risks.append("بودجه بسیار کمتر از برآورد — یا کاهش محدوده یا افزایش مبلغ")
            elif ratio < 0.75:
                add("budget_fit",
                    f"بودجه ({project.budget_toman:,} تومان) کمتر از برآورد ماست "
                    f"({estimate:,} تومان)", -12)
                risks.append("نیاز به مذاکره روی مبلغ یا محدوده")
            elif ratio >= 1.5:
                add("budget_fit",
                    f"بودجه ({project.budget_toman:,} تومان) از برآورد ما "
                    f"({estimate:,} تومان) بیشتر است — حاشیه‌ی سود خوب", 5)

    if fit == "yes":
        add("deliverable", "خروجیِ پروژه فایل/کد است و کاملاً قابل تحویل توسط آرنا است",
            int(sc.get("bonus_clear_deliverable", 5)))

    # ---------- زمان ----------
    max_hours = cfg.max_hours
    time_flag = "ok"
    if hours > max_hours * 1.5:
        add("time", f"زمان‌بر است ({hours:g} ساعت — بیش از {max_hours * 1.5:g} ساعت)",
            -20)
        blockers.append("زمان اجرا از سقف مجاز خیلی بیشتر است")
        time_flag = "too_long"
    elif hours > max_hours:
        add("time", f"زمان اجرا ({hours:g} ساعت) کمی از سقف {max_hours:g} ساعت بیشتر است",
            -8)
        time_flag = "long"

    # ---------- تصمیم نهایی ----------
    min_candidate = int(sc.get("min_score_candidate", 70))
    min_review = int(sc.get("min_score_review", 45))

    # آگهی‌های استخدامی (نه پروژه‌ی مشخص) قابل اجرا نیستند
    hiring = [f for f in (project.flags or []) if "استخدام" in f]
    if hiring:
        add("hiring_ad", "این آگهی از نوع استخدام/جذب نیرو است، نه یک پروژه با محدوده و مبلغ مشخص",
            -20)
        blockers.append("آگهی استخدامی (نه پروژه‌ی مشخص)")
        needs_you.append({
            "kind": "delivery_format",
            "text": "این آگهی استخدامی است؛ برای اقدام باید ابتدا با کارفرما به‌صورت "
                    "پروژه‌ای (مبلغ و خروجی مشخص) به توافق برسید.",
        })

    # قانون کسب‌وکار: بودجه‌های خیلی پایین‌تر از کفِ ما ارزش پیشنهاد دادن ندارند
    if project.budget_toman and project.budget_toman < 0.6 * cfg.min_price:
        add("below_floor",
            f"بودجه ({project.budget_toman:,} تومان) بسیار کمتر از حداقل مبلغ قابل قبول "
            f"({cfg.min_price:,} تومان) است", -30)
        blockers.append("بودجه زیرِ کفِ ما")

    score = max(0, min(100, score))

    if (fit == "no" or time_flag == "too_long"
            or "پرداخت مشروط به نتیجه/بازدهی" in blockers
            or "بودجه زیرِ کفِ ما" in blockers
            or "آگهی استخدامی (نه پروژه‌ی مشخص)" in blockers):
        verdict = "rejected"
    elif score >= min_candidate and time_flag == "ok":
        verdict = "candidate"
    elif score >= min_review:
        verdict = "review"
    else:
        verdict = "rejected"

    schedule_days = math.ceil(hours / max(cfg.work_hours_per_day, 1))
    client_days = project.client_deadline_days

    # نکته: کارهای مربوط به «ثبت پیشنهاد» و «تایید» در ماژول reporting ساخته می‌شوند،
    # چون به تصمیم‌ها و وضعیتِ صفِ کارها وابسته‌اند.

    return {
        "category": category,
        "category_label": rule["label"],
        "arena_fit": fit,
        "fit_label": fit_label,
        "score": score,
        "verdict": verdict,
        "est_hours": hours,
        "schedule_days": schedule_days,
        "client_days": client_days,
        "time_flag": time_flag,
        "reasons": reasons,
        "blockers": blockers,
        "risks": risks,
        "needs_you": needs_you,
        "hour_notes": hour_notes,
        "deliverables": list(rule["deliverables"]),
        "tech": list(rule["tech"]),
        "features": extract_bullets(project.description or "")[:8],
        "deadline_pressure": bool(client_days and schedule_days > client_days),
    }


def screen_all(projects: list[Project], cfg: Config) -> None:
    for p in projects:
        p.screening = screen(p, cfg)
