"""ساخت دموی گرافیکی (پیش‌نمایش ظاهری) برای هر پروژه‌ی کاندید.

هدف: کارفرما بتواند «دقیقاً ببیند چه چیزی ساخته خواهد شد»، اما نتواند از آن
استفاده کند یا آن را به‌عنوان محصول نهایی بردارد. برای هر پروژه دو فایل ساخته
می‌شود:

  index.html    نسخه‌ی داخلی (با امتیاز، برآورد ساعت، لینک آگهی و …)
  client.html   نسخه‌ی ارسال به کارفرما (بدون اطلاعات داخلی، با واترمارک)

هر دو نسخه:
  - یک طرح گرافیکی کامل و راست‌چین از خروجی پروژه هستند (هدر، قهرمان، خدمات،
    محصولات، درباره، تماس، پاورقی) یا صفحاتِ واقعی اپ/داشبورد پروژه
  - واترمارکِ موربِ سراسری دارند
  - تعاملات‌شان قفل است (کلیک، فرم، انتخاب متن، راست‌کلیک، ذخیره)
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .models import Project
from .normalize import clean_text, slugify, to_persian_digits
from . import design_system as ds

# ---------------------------------------------------------------------------
# استایل‌ها
# ---------------------------------------------------------------------------
CSS = """
:root{--p:#3b5bdb;--a:#22b8cf;--ink:#161a2b;--mut:#6b7280;--line:#e6e9f2;--bg:#f6f7fc}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:"Vazirmatn","IRANSans","B Nazanin","Segoe UI",Tahoma,sans-serif;
direction:rtl;line-height:1.9;font-size:15px;-webkit-user-select:none;user-select:none}
img,svg{max-width:100%;display:block}
a{color:var(--p);text-decoration:none;cursor:default}
.wrap{max-width:1120px;margin:0 auto;padding:0 18px}
h1,h2,h3{margin:0 0 10px;line-height:1.6}
.muted{color:var(--mut);font-size:13.5px}
.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:20px;margin-bottom:16px;
box-shadow:0 6px 22px rgba(21,32,70,.05)}
.grid{display:grid;gap:14px}
.g3{grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.g4{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}
.btn{display:inline-block;background:var(--p);color:#fff;border:0;border-radius:12px;padding:11px 22px;
font:inherit;cursor:default}
.btn.ghost{background:#fff;color:var(--p);border:1px solid #ccd6f8}
.btn.alt{background:var(--a)}
.chip{display:inline-block;background:#eef2ff;border:1px solid #d9e1fb;color:#2b3f8f;
border-radius:999px;padding:3px 12px;font-size:12px;margin-left:6px}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:11.5px;border:1px solid}
.b-ok{background:#e7f8ef;color:#1a7f4b;border-color:#b7e6cd}
.b-wait{background:#fff4e0;color:#8a5a00;border-color:#ffe0a8}
.b-run{background:#e8f0ff;color:#2b4cb8;border-color:#c5d5ff}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{padding:9px 10px;border-bottom:1px solid #eceff7;text-align:right}
th{background:#f3f5fb;color:#4a5578;font-size:12.5px}
input,select,textarea{font:inherit;padding:10px 12px;border:1px solid #dbe1ee;border-radius:11px;
width:100%;background:#fbfcff;color:#8a91a6}
input::placeholder,textarea::placeholder{color:#a9b0c3}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.kpi{background:linear-gradient(160deg,#fff,#f4f6fd);border:1px solid var(--line);border-radius:14px;padding:14px}
.kpi .k{font-size:12.5px;color:var(--mut)}
.kpi .v{font-size:23px;font-weight:800;margin-top:2px}
.kpi .d{font-size:12px;color:#22a06b}
.steps{counter-reset:s;margin-top:6px}
.step{position:relative;padding:0 34px 16px 0;border-right:2px solid #e3e8f5}
.step:last-child{border-right-color:transparent}
.step:before{counter-increment:s;content:counter(s);position:absolute;right:-13px;top:0;width:24px;height:24px;
border-radius:50%;background:var(--p);color:#fff;font-size:12px;display:flex;align-items:center;justify-content:center}
.steps .t{font-weight:700}
pre.json{background:#0f172a;color:#d7e3ff;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;
border-radius:12px;padding:14px;overflow:auto;max-height:260px;text-align:left;direction:ltr}
.bar{background:linear-gradient(90deg,var(--p),var(--a));border-radius:4px 4px 0 0}
.log{background:#111827;color:#c8f0d8;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;
border-radius:12px;padding:12px;height:150px;overflow:auto;line-height:1.7}
.progress{height:9px;background:#e9edf7;border-radius:999px;overflow:hidden;margin:10px 0}
.progress i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--p),var(--a));transition:width .25s}
@media(max-width:640px){.wrap{padding:0 12px}}
"""

CSS_MOCK = """
.mockbar{background:#0f1730;color:#c7d2fe;font-size:12px;padding:7px 14px;display:flex;gap:10px;
align-items:center;justify-content:center;flex-wrap:wrap;border-radius:0 0 14px 14px}
.mockbar b{color:#fff}
.mockwin{border:1px solid #dfe4f2;border-radius:16px;overflow:hidden;background:#fff;
box-shadow:0 18px 50px rgba(19,30,66,.10)}
.dots{display:flex;gap:6px;padding:9px 12px;background:#f3f5fb;border-bottom:1px solid #e6e9f2}
.dots i{width:10px;height:10px;border-radius:50%;background:#d7dceb;display:block}
.mh{position:sticky;top:0;z-index:5;background:rgba(255,255,255,.94);backdrop-filter:blur(8px);
border-bottom:1px solid #eceff7}
.mh .in{display:flex;align-items:center;justify-content:space-between;padding:12px 18px;gap:14px}
.logo{display:flex;align-items:center;gap:9px;font-weight:800;font-size:16px}
.logo span.m{width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,var(--p),var(--a));
display:grid;place-items:center;color:#fff;font-size:15px}
.nav{display:flex;gap:18px;font-size:14px;color:#4b5570}
.hero{padding:44px 18px 34px;color:#fff;position:relative;overflow:hidden}
.hero:after{content:"";position:absolute;inset:auto -10% -60% 40%;height:220px;background:rgba(255,255,255,.10);
border-radius:50%}
.hero .in{position:relative;z-index:2;display:grid;grid-template-columns:1.15fr .85fr;gap:26px;align-items:center}
.hero h1{font-size:31px;line-height:1.45;margin:0 0 12px}
.hero p{margin:0 0 20px;opacity:.93;font-size:15.5px}
.hero .cta{display:flex;gap:10px;flex-wrap:wrap}
.sect{padding:34px 18px}
.sect.alt{background:#f8f9fe}
.sect h2{text-align:center;font-size:22px}
.sect .sub{text-align:center;color:var(--mut);margin-bottom:20px;font-size:14px}
.card2{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px}
.card2 .ic{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;margin-bottom:10px;
background:linear-gradient(135deg,#eef2ff,#e6fbfd);font-size:20px}
.card2 .t{font-weight:800;margin-bottom:4px}
.card2 .d{color:var(--mut);font-size:13.5px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;text-align:center}
.stat .v{font-size:26px;font-weight:800;color:var(--p)}
.stat .k{font-size:13px;color:var(--mut)}
.prod{background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden}
.prod .ph{height:150px;display:grid;place-items:center}
.prod .bd{padding:12px}
.prod .n{font-weight:700;font-size:14px}
.prod .pr{color:#1a7f4b;font-weight:800;margin-top:4px;font-size:14px}
.prod .old{text-decoration:line-through;color:#a6adbd;font-size:12px;margin-right:6px}
.quote{border:1px solid var(--line);border-radius:16px;padding:16px;background:#fff}
.quote .txt{color:#4b5570;font-size:14px}
.quote .who{display:flex;align-items:center;gap:10px;margin-top:12px}
.quote .av{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,var(--p),var(--a))}
.formrow{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.field{margin-bottom:10px}
.field label{display:block;font-size:13px;margin-bottom:5px;color:#4b5570}
.mfoot{background:#0f1730;color:#aab6d8;padding:26px 18px;font-size:13.5px}
.mfoot .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:18px}
.mfoot h4{color:#fff;margin:0 0 8px;font-size:14px}
.mfoot .bt{border-top:1px solid #25304f;margin-top:18px;padding-top:12px;text-align:center;color:#7f8db4;font-size:12px}
.langbar{display:flex;gap:6px;justify-content:center;margin:14px 0 0}
.langbar button{background:#fff;border:1px solid #d7deef;border-radius:999px;padding:6px 16px;font:inherit;
font-size:13px;color:#39405a}
.langbar button.on{background:var(--p);border-color:var(--p);color:#fff}
@media(max-width:760px){.hero .in{grid-template-columns:1fr}.formrow{grid-template-columns:1fr}.nav{display:none}}
"""

CSS_LOCK = """
#wm{position:fixed;inset:0;z-index:9997;pointer-events:none;opacity:.13;
background-repeat:repeat;background-size:340px 190px}
#guard{position:fixed;inset:0;z-index:9998;cursor:not-allowed}
#note{position:fixed;z-index:9999;left:50%;bottom:26px;transform:translateX(-50%);
background:#111827;color:#fff;border-radius:14px;padding:12px 20px;font-size:14px;
box-shadow:0 12px 40px rgba(0,0,0,.35);opacity:0;transition:opacity .2s;pointer-events:none;max-width:90vw}
#note.on{opacity:1}
#ribbon{position:fixed;top:0;left:0;right:0;z-index:9996;background:linear-gradient(90deg,#111827,#1f2b4d);
color:#ffd9a8;font-size:12.5px;text-align:center;padding:5px 10px}
body{padding-top:26px}
"""

LOCK_JS = """
(function(){
  var t, note=document.getElementById('note');
  function show(msg){
    note.textContent=msg; note.classList.add('on');
    clearTimeout(t); t=setTimeout(function(){note.classList.remove('on')},2600);
  }
  document.getElementById('guard').addEventListener('click',function(e){
    e.preventDefault(); e.stopPropagation();
    show('این فقط یک پیش‌نمایش گرافیکی است؛ نسخه‌ی قابل استفاده پس از تایید قرارداد تحویل می‌شود.');
  },true);
  document.addEventListener('contextmenu',function(e){e.preventDefault();show('کپی/ذخیره در نسخه‌ی نمایشی غیرفعال است.')});
  document.addEventListener('keydown',function(e){
    var k=(e.key||'').toLowerCase();
    if((e.ctrlKey||e.metaKey) && ['s','u','p','c','x','a'].indexOf(k)>=0){e.preventDefault();show('در نسخه‌ی نمایشی غیرفعال است.')}
  });
  document.addEventListener('selectstart',function(e){e.preventDefault()});
  document.addEventListener('dragstart',function(e){e.preventDefault()});
  document.querySelectorAll('a').forEach(function(a){
    a.setAttribute('href','#'); a.addEventListener('click',function(e){e.preventDefault()});
  });
  document.querySelectorAll('form').forEach(function(f){f.addEventListener('submit',function(e){e.preventDefault()})});
  document.querySelectorAll('input,select,textarea,button').forEach(function(el){el.disabled=true});
  window.addEventListener('beforeprint',function(e){e.preventDefault()});
})();
"""

# واترمارکِ موربِ سراسری (SVG داخلی، بدون نیاز به اینترنت)
def _watermark_svg(text: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="340" height="190">'
        '<text x="0" y="120" transform="rotate(-28 0 120)" font-size="26" font-family="Tahoma,sans-serif" '
        f'fill="#111827" opacity="0.55">{text}</text></svg>'
    )
    from urllib.parse import quote
    return "url('data:image/svg+xml;utf8," + quote(svg) + "')"


LOCK_HTML = """
<div id="wm" style="background-image:{wm}"></div>
<div id="guard"></div>
<div id="ribbon">پیش‌نمایش گرافیکیِ نمونه — فقط برای مشاهده؛ در این نسخه هیچ چیز قابل استفاده نیست</div>
<div id="note"></div>
"""

# ---------------------------------------------------------------------------
# تشخیص نوع پروژه و شخصی‌سازی محتوا
# ---------------------------------------------------------------------------
ARCHETYPE_RULES = [
    ("gold_shop", [r"طلا", r"جواهر", r"زرگر"]),
    ("med_equipment", [r"تجهیزات پزشکی", r"تجهیزات آزمایشگاه", r"تجهیزات دندانپزشکی"]),
    ("clinic", [r"کلینیک", r"درمان", r"دندانپزشک", r"دندان", r"مطب", r"بیمارستان",
                r"زیبایی", r"فیزیوتراپ", r"روانشناس", r"ویزیت", r"بیمار"]),
    ("industrial", [r"لیفتراک", r"تولیدی", r"صنعت", r"کارخانه", r"ماشین آلات", r"مکانیک"]),
    ("restaurant", [r"رستوران", r"کافه", r"فست فود", r"منو"]),
    ("realestate", [r"املاک", r"ملک", r"مسکن", r"آپارتمان"]),
    ("education", [r"آموزش", r"دوره", r"مدرسه", r"آموزشگاه", r"دانشجو"]),
    ("shop", [r"فروشگاه", r"ecommerce", r"محصول", r"دیتا اینتری", r"دیجی ?کالا"]),
    ("corporate", [r"شرکت", r"سازمان", r"شرکتی", r"سایت شرکتی", r"معرفی شرکت"]),
]

ARCHETYPE_LABELS = {
    "clinic": "وب‌سایت کلینیک/درمانی",
    "gold_shop": "فروشگاه اینترنتی طلا و جواهر",
    "med_equipment": "وب‌سایت شرکت تجهیزات پزشکی",
    "industrial": "وب‌سایت شرکتی/صنعتی",
    "restaurant": "وب‌سایت رستوران/کافه",
    "realestate": "وب‌سایت املاک",
    "education": "وب‌سایت آموزشی",
    "shop": "فروشگاه اینترنتی",
    "corporate": "وب‌سایت شرکتی",
}

PALETTES = {
    "clinic": ("#0e9f6e", "#22b8cf", "linear-gradient(135deg,#0b6b4f 0%,#0e9f6e 55%,#22b8cf 100%)"),
    "gold_shop": ("#a16207", "#d97706", "linear-gradient(135deg,#7c4a03 0%,#a16207 55%,#e0a53a 100%)"),
    "med_equipment": ("#1d4ed8", "#0ea5e9", "linear-gradient(135deg,#12306b 0%,#1d4ed8 55%,#0ea5e9 100%)"),
    "industrial": ("#b45309", "#64748b", "linear-gradient(135deg,#7c2d12 0%,#b45309 55%,#94a3b8 100%)"),
    "restaurant": ("#b91c1c", "#f59e0b", "linear-gradient(135deg,#7f1d1d 0%,#b91c1c 55%,#f59e0b 100%)"),
    "realestate": ("#1e40af", "#0891b2", "linear-gradient(135deg,#172554 0%,#1e40af 55%,#0891b2 100%)"),
    "education": ("#6d28d9", "#0ea5e9", "linear-gradient(135deg,#4c1d95 0%,#6d28d9 55%,#0ea5e9 100%)"),
    "shop": ("#db2777", "#f59e0b", "linear-gradient(135deg,#9d174d 0%,#db2777 55%,#f59e0b 100%)"),
    "corporate": ("#1e3a8a", "#0ea5e9", "linear-gradient(135deg,#0f2350 0%,#1e3a8a 55%,#0ea5e9 100%)"),
}

STOPWORDS = [
    "طراحی و پیاده سازی", "طراحی و پیاده‌سازی", "پیاده سازی", "پیاده‌سازی", "طراحی", "بازطراحی",
    "ساخت", "ایجاد", "افزودن", "اضافه کردن", "ارتقای", "ارتقا", "تکمیل", "آماده سازی", "آماده‌سازی",
    "وب سایت", "وبسایت", "وب‌سایت", "سایت", "وب اپلیکیشن", "اپلیکیشن", "وردپرسی", "وردپرس",
    "فروشگاهی", "فروشگاه اینترنتی", "نسخه بتا", "نسخه", "موجود", "جدید", "یک", "دو", "برای", "به",
    "با", "و", "یا", "کمک", "هوش مصنوعی", "پروژه", "اسکریپت", "افزونه", "زبان انگلیسی", "زبان",
    "انگلیسی", "قرار دادن", "در سایت", "در", "برنامه نویسی", "انجام", "سفارش", "افزودن محصول",
]

FALLBACK_BRAND = {
    "clinic": "کلینیک تخصصی سلامت",
    "gold_shop": "گالری طلا و جواهر درخشان",
    "med_equipment": "شرکت تجهیزات پزشکی پارسیان",
    "industrial": "گروه صنعتی آریا",
    "restaurant": "رستوران سنتی نارنج",
    "realestate": "املاک آسمان",
    "education": "آکادمی آموزشی فرانگرش",
    "shop": "فروشگاه اینترنتی شما",
    "corporate": "شرکت شما",
}


def _brand_from_title(title: str, archetype: str) -> str:
    t = clean_text(title)
    for w in STOPWORDS:
        t = re.sub(rf"\b{re.escape(w)}\b", " ", t)
    t = re.sub(r"[()\[\]/،,.:؛;؟?\-–—]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = t[:46].strip()
    if len(t) < 4:
        return FALLBACK_BRAND[archetype]
    return t


def detect_archetype(project: Project, screening: dict) -> str:
    hay = f"{project.title} {project.description}".lower()
    for name, patterns in ARCHETYPE_RULES:
        for p in patterns:
            if re.search(p, hay):
                return name
    return "corporate"


# ---------------------------------------------------------------------------
# محتوای هر نوع پروژه
# ---------------------------------------------------------------------------
def _content(archetype: str, brand: str) -> dict:
    """محتوای نمونه‌ی متناسب با پروژه (فارسی و در صورت نیاز انگلیسی)."""
    fa: dict = {
        "clinic": {
            "tagline": "مراقبت تخصصی، با آرامش خاطر",
            "nav": ["خانه", "خدمات", "پزشکان", "نوبت‌دهی", "درباره ما", "تماس"],
            "hero_t": f"{brand}؛ جایی که درمان با آرامش همراه می‌شود",
            "hero_d": "نوبت‌دهی آنلاین، پرونده‌ی الکترونیک بیمار و پیگیری درمان — همه در یک سایت سبک و سریع که روی موبایل هم عالی کار می‌کند.",
            "cta1": "رزرو نوبت آنلاین", "cta2": "مشاهده‌ی خدمات",
            "services": [
                ("🩺", "ویزیت تخصصی", "رزرو نوبت بر اساس تخصص و زمان آزاد هر پزشک"),
                ("🦷", "خدمات تخصصی", "معرفی کامل خدمات با توضیح، تعرفه و مدت‌زمان هر خدمت"),
                ("📋", "پرونده‌ی الکترونیک", "تاریخچه‌ی مراجعات، نسخه‌ها و پیگیری‌های درمانی بیمار"),
                ("🔔", "یادآوری نوبت", "پیامک خودکار ۲۴ ساعت پیش از نوبت به بیمار"),
                ("💳", "پرداخت آنلاین", "پرداخت بیعانه و هزینه‌ی ویزیت از درون سایت"),
                ("📞", "پشتیبانی", "پاسخ‌گویی آنلاین و ثبت درخواست مشاوره"),
            ],
            "stats": [("۲۴+", "پزشک متخصص"), ("۱۸هزار", "بیمار فعال"), ("۹۸٪", "رضایت مراجعان"), ("۱۵ ثانیه", "زمان رزرو نوبت")],
            "products": [],
            "about": f"{brand} با تیمی از پزشکان متخصص و تجهیزات به‌روز، خدمات درمانی را در محیطی آرام ارائه می‌دهد. هدف این سایت، کوتاه‌تر کردن مسیر بیمار تا نوبت و پیگیری درمان است.",
            "testimonials": [
                "نوبت‌گیری آنلاین کار را خیلی راحت کرده؛ بدون تماس تلفنی وقت گرفتم.", "سارا م.",
                "طراحی سایت تمیز و قابل اعتماد است؛ بیمارها راحت پیدایش می‌کنند.", "دکتر احمدی",
            ],
            "quote_items": ["دریافت نوبت آنلاین", "مشاهده‌ی سوابق", "پرداخت اینترنتی", "پشتیبانی آنلاین"],
        },
        "gold_shop": {
            "tagline": "درخشش اصالت در هر خرید",
            "nav": ["خانه", "محصولات", "قیمت روز طلا", "درباره ما", "تماس"],
            "hero_t": f"{brand}؛ خرید آنلاین طلا با قیمت روز و فاکتور رسمی",
            "hero_d": "قیمت‌ها هر ۵ دقیقه به‌روز می‌شود، اجرت و سود به‌صورت شفاف جداگانه نمایش داده می‌شود و هر سفارش با بیمه ارسال می‌گردد.",
            "cta1": "مشاهده‌ی محصولات", "cta2": "قیمت لحظه‌ای طلا",
            "services": [
                ("💰", "قیمت لحظه‌ای", "نمایش خودکار قیمت طلا، اجرت و سود روی هر محصول"),
                ("🔎", "فیلتر هوشمند", "جستجو بر اساس عیار، وزن، رنگ و بازه‌ی قیمت"),
                ("🧾", "فاکتور رسمی", "صدور فاکتور با جزئیات اجرت و مالیات"),
                ("🚚", "ارسال بیمه‌شده", "ارسال رایگان بالای سقف خرید، با بیمه‌ی کامل"),
                ("↩️", "۷ روز ضمانت بازگشت", "امکان بازگشت کالا طبق شرایط"),
                ("📦", "پیگیری سفارش", "پنل پیگیری مراحل سفارش برای مشتری"),
            ],
            "stats": [("۱,۲۰۰+", "محصول فعال"), ("هر ۵ دقیقه", "به‌روزرسانی قیمت"), ("۴.۹/۵", "رضایت مشتریان"), ("۴۸ ساعت", "زمان ارسال")],
            "products": [
                ("انگشتر طلا زنانه", "۱۲,۴۵۰,۰۰۰", "۱۳,۲۰۰,۰۰۰", "#f5e7c1"),
                ("گوشواره آویز نگین‌دار", "۸,۹۰۰,۰۰۰", "۹,۴۰۰,۰۰۰", "#f7e3c8"),
                ("سرویس نیم‌ست طلا", "۳۴,۵۰۰,۰۰۰", "۳۶,۰۰۰,۰۰۰", "#f3dcae"),
                ("النگو طلا تراش‌خورده", "۲۱,۷۰۰,۰۰۰", "۲۳,۱۰۰,۰۰۰", "#f6e9cf"),
                ("پلاک اسم طلا", "۶,۳۰۰,۰۰۰", "۶,۹۰۰,۰۰۰", "#f8ecd6"),
                ("سکه و تمام‌بهار", "۷۲,۰۰۰,۰۰۰", "۷۳,۵۰۰,۰۰۰", "#f1dca9"),
            ],
            "about": f"{brand} با سابقه‌ی درخشان در طراحی و فروش طلا و جواهر، خریدی شفاف و مطمئن را تجربه می‌کند: قیمت بر اساس نرخ روز، فاکتور رسمی و ارسال بیمه‌شده.",
            "testimonials": [
                "قیمت‌ها شفاف و دقیق بود؛ با خیال راحت خرید کردم.", "مریم ح.",
                "ارسال سریع و بسته‌بندی شیک؛ حتماً دوباره می‌خرم.", "علی ر.",
            ],
            "quote_items": ["قیمت لحظه‌ای", "فاکتور رسمی", "ارسال بیمه‌شده", "پنل پیگیری سفارش"],
        },
        "med_equipment": {
            "tagline": "تأمین تجهیزات پزشکی با استاندارد جهانی",
            "nav": ["خانه", "دسته‌بندی تجهیزات", "پروژه‌ها", "گواهی‌نامه‌ها", "درباره ما", "تماس"],
            "hero_t": f"{brand}؛ مرجع تأمین و پشتیبانی تجهیزات پزشکی",
            "hero_d": "کاتالوگ کامل تجهیزات با مشخصات فنی، گواهی‌نامه‌ها و امکان درخواست پیش‌فاکتور آنلاین برای بیمارستان‌ها و کلینیک‌ها.",
            "cta1": "دریافت کاتالوگ", "cta2": "درخواست پیش‌فاکتور",
            "services": [
                ("🏥", "تجهیزات بیمارستانی", "تخت، ونتیلاتور، مانیتور و تجهیزات بخش ویژه"),
                ("🔬", "تجهیزات آزمایشگاهی", "سانتریفیوژ، انکوباتور و دستگاه‌های تشخیصی"),
                ("🛠️", "خدمات پس از فروش", "نصب، راه‌اندازی، کالیبراسیون و گارانتی"),
                ("📑", "گواهی‌نامه‌ها", "ISO، استاندارد ملی و تأییدیه‌ی وزارت بهداشت"),
                ("🚚", "ارسال سراسری", "ارسال به کل کشور با بسته‌بندی ایمن"),
                ("🧑‍🔧", "تعمیر و نگهداری", "قرارداد سرویس دوره‌ای برای مراکز درمانی"),
            ],
            "stats": [("۸۵۰+", "قلم کالا"), ("۳۲", "استان تحت پوشش"), ("۲۴ ماه", "گارانتی"), ("۴۸ ساعت", "پاسخ به استعلام")],
            "products": [
                ("مانیتور علائم حیاتی مدل M7", "استعلامی", "", "#dbe7f8"),
                ("دستگاه سونوگرافی پرتابل", "استعلامی", "", "#d8e6f5"),
                ("تخت بیمارستانی برقی ۳ شکن", "استعلامی", "", "#e2ecf9"),
                ("سانتریفیوژ آزمایشگاهی ۱۲ شاخه", "استعلامی", "", "#dfe9f7"),
                ("ونتیلاتور ICU مدل V5", "استعلامی", "", "#d9e4f4"),
                ("اتوکلاو ۲۳ لیتری", "استعلامی", "", "#e4eefb"),
            ],
            "about": f"{brand} تأمین‌کننده‌ی تخصصی تجهیزات پزشکی و آزمایشگاهی است؛ از مشاوره‌ی انتخاب دستگاه تا نصب، آموزش و نگهداری در کنار مراکز درمانی.",
            "testimonials": [
                "پاسخ‌گویی سریع و تجهیزات باکیفیت؛ روند خرید کاملاً شفاف بود.", "مدیر تدارکات بیمارستان",
                "نصب و آموزش دستگاه‌ها به‌موقع انجام شد.", "سرپرست آزمایشگاه",
            ],
            "quote_items": ["کاتالوگ فنی", "درخواست پیش‌فاکتور", "مقایسه‌ی محصولات", "فرم استعلام"],
        },
        "industrial": {
            "tagline": "تولید قدرتمند، تحویل به‌موقع",
            "nav": ["خانه", "محصولات", "خطوط تولید", "گواهی‌ها", "درباره ما", "تماس"],
            "hero_t": f"{brand}؛ تولیدکننده‌ی معتبر با استاندارد صنعتی",
            "hero_d": "معرفی خطوط تولید، ظرفیت ساخت، مشخصات فنی محصولات و امکان ثبت درخواست همکاری برای نمایندگان و مشتریان صنعتی.",
            "cta1": "مشاهده‌ی محصولات", "cta2": "درخواست همکاری",
            "services": [
                ("🏭", "ظرفیت تولید", "نمایش ظرفیت ماهانه و زمان تحویل هر خط تولید"),
                ("⚙️", "مشخصات فنی", "جدول مشخصات، نقشه‌ها و فایل‌های PDF قابل دانلود"),
                ("🛡️", "کنترل کیفیت", "گواهی‌های بازرسی و استانداردهای تولید"),
                ("🤝", "شبکه نمایندگان", "جستجوی نماینده بر اساس استان"),
                ("📞", "پشتیبانی فنی", "ثبت تیکت و پیگیری خدمات پس از فروش"),
                ("📄", "مناقصات", "اطلاع‌رسانی فراخوان‌ها و همکاری‌ها"),
            ],
            "stats": [("۴۰ سال", "تجربه"), ("۱۲۰", "نیروی متخصص"), ("۹۵٪", "تحویل به‌موقع"), ("۲۶", "نماینده فعال")],
            "products": [
                ("لیفتراک دیزلی ۳ تن", "استعلامی", "", "#dfe3ee"),
                ("لیفتراک برقی ۱.۵ تن", "استعلامی", "", "#e6e9f3"),
                ("استacker دستی ۲ تن", "استعلامی", "", "#dde1ec"),
                ("ریچتراک ۱.۵ تن", "استعلامی", "", "#e8ebf5"),
                ("جک پالت ۲.۵ تن", "استعلامی", "", "#dce0eb"),
                ("قطعات یدکی و سرویس", "استعلامی", "", "#e9ecf6"),
            ],
            "about": f"{brand} با اتکا به نیروی متخصص و خطوط تولید مدرن، محصولات صنعتی با کیفیت پایدار عرضه می‌کند و شبکه‌ی خدمات پس از فروش گسترده‌ای دارد.",
            "testimonials": [
                "کیفیت ساخت و زمان تحویل دقیق بود.", "مدیر خرید کارخانه",
                "پشتیبانی فنی سریع پاسخ داد.", "مدیر انبار",
            ],
            "quote_items": ["کاتالوگ محصولات", "جدول مشخصات فنی", "درخواست نمایندگی", "فرم تماس"],
        },
        "shop": {
            "tagline": "خریدی آسان‌تر از همیشه",
            "nav": ["خانه", "دسته‌بندی‌ها", "پیشنهاد ویژه", "پیگیری سفارش", "درباره ما", "تماس"],
            "hero_t": f"{brand}؛ فروشگاه اینترنتی با تجربه‌ی خرید سریع",
            "hero_d": "جستجوی سریع، فیلتر دقیق، مقایسه‌ی کالا، سبد خرید و پرداخت آنلاین — طراحی‌شده برای افزایش فروش و راحتی مشتری.",
            "cta1": "شروع خرید", "cta2": "پیگیری سفارش",
            "services": [
                ("🔍", "جستجوی سریع", "جستجوی لحظه‌ای در نام، برند و ویژگی‌ها"),
                ("🎯", "فیلتر هوشمند", "فیلتر بر اساس قیمت، برند، رنگ و موجودی"),
                ("🛒", "سبد خرید پیشرفته", "ذخیره‌ی سبد، کد تخفیف و محاسبه‌ی ارسال"),
                ("💳", "پرداخت آنلاین", "اتصال به درگاه پرداخت و پرداخت اقساطی"),
                ("📦", "پیگیری سفارش", "پنل پیگیری مراحل سفارش برای مشتری"),
                ("⭐", "امتیاز و نظر", "ثبت نظر و امتیاز برای هر محصول"),
            ],
            "stats": [("۳,۴۰۰+", "کالای فعال"), ("۱۸ ثانیه", "میانگین جستجو"), ("۹۶٪", "سفارش‌های موفق"), ("۲۴/۷", "دسترسی")],
            "products": [
                ("کوله‌پشتی لپ‌تاپ ضدآب", "۱,۲۹۰,۰۰۰", "۱,۵۴۰,۰۰۰", "#eef2ff"),
                ("هدفون بلوتوثی ANC", "۲,۴۵۰,۰۰۰", "۲,۸۰۰,۰۰۰", "#eaf6ff"),
                ("ساعت هوشمند اسپرت", "۳,۱۰۰,۰۰۰", "۳,۵۰۰,۰۰۰", "#f1ecff"),
                ("ماوس بی‌سیم ارگونومیک", "۶۵۰,۰۰۰", "۷۹۰,۰۰۰", "#eafaf3"),
                ("پاوربانک ۲۰۰۰۰ میلی‌آمپر", "۱,۱۰۰,۰۰۰", "۱,۳۵۰,۰۰۰", "#fff3e8"),
                ("پایه نگهدارنده موبایل", "۳۲۰,۰۰۰", "۳۹۰,۰۰۰", "#f6f7fc"),
            ],
            "about": f"{brand} با هدف تجربه‌ی خرید آسان شکل گرفته است: دسته‌بندی روشن، فیلتر دقیق و فرایند پرداخت کوتاه.",
            "testimonials": [
                "فرایند خرید خیلی سریع و راحت بود.", "نازنین ک.",
                "پیگیری سفارش عالی کار می‌کند.", "حسین م.",
            ],
            "quote_items": ["جستجو و فیلتر", "سبد خرید", "پرداخت آنلاین", "پنل پیگیری سفارش"],
        },
        "corporate": {
            "tagline": "اعتماد، تخصص، رشد",
            "nav": ["خانه", "خدمات", "پروژه‌ها", "درباره ما", "مقالات", "تماس"],
            "hero_t": f"{brand}؛ وب‌سایت رسمی و مدرن برای معرفی خدمات شما",
            "hero_d": "معرفی خدمات، نمونه‌کارها، تیم و راه‌های ارتباطی در قالبی حرفه‌ای که اعتماد مخاطب را جلب می‌کند.",
            "cta1": "درخواست مشاوره", "cta2": "مشاهده‌ی خدمات",
            "services": [
                ("🎯", "معرفی خدمات", "شرح دقیق خدمات با مزایا و نمونه‌کار"),
                ("🏆", "نمونه‌کارها", "گالری پروژه‌ها با فیلتر دسته‌بندی"),
                ("👥", "تیم ما", "معرفی اعضا، تخصص‌ها و سوابق"),
                ("📈", "دستاوردها", "آمار و شاخص‌های کلیدی عملکرد"),
                ("📝", "وبلاگ", "انتشار مقاله و خبر با مدیریت محتوا"),
                ("📨", "فرم درخواست", "ثبت درخواست مشاوره با اطلاع‌رسانی ایمیلی"),
            ],
            "stats": [("۱۲ سال", "سابقه"), ("۳۵۰+", "پروژه انجام‌شده"), ("۹۸٪", "رضایت مشتریان"), ("۲۴ ساعت", "پاسخ‌گویی")],
            "products": [],
            "about": f"{brand} با تکیه بر تخصص و تجربه، راهکارهایی ارائه می‌کند که کسب‌وکار مشتریان را رشد می‌دهد.",
            "testimonials": [
                "همکاری حرفه‌ای و تحویل به‌موقع.", "مدیرعامل",
                "کیفیت کار فراتر از انتظار بود.", "مدیر پروژه",
            ],
            "quote_items": ["معرفی خدمات", "نمونه‌کارها", "وبلاگ", "فرم درخواست مشاوره"],
        },
        "restaurant": {
            "tagline": "طعمی که می‌ماند",
            "nav": ["خانه", "منو", "رزرو میز", "گالری", "درباره ما", "تماس"],
            "hero_t": f"{brand}؛ رزرو آنلاین میز و مشاهده‌ی منو",
            "hero_d": "منوی کامل با قیمت و ترکیبات، رزرو میز بر اساس ساعت و ظرفیت، و سفارش آنلاین غذا برای بیرون‌بر.",
            "cta1": "رزرو میز", "cta2": "مشاهده‌ی منو",
            "services": [
                ("🍽️", "منوی آنلاین", "دسته‌بندی غذاها با قیمت، تصویر و ترکیبات"),
                ("🪑", "رزرو میز", "انتخاب تاریخ، ساعت و تعداد نفرات"),
                ("🛵", "سفارش بیرون‌بر", "سبد خرید و پرداخت آنلاین"),
                ("📍", "مسیریابی", "آدرس، نقشه و ساعات کاری"),
                ("🎉", "رویدادها", "پذیرایی مراسم و سفارش‌های سازمانی"),
                ("⭐", "نظرات", "ثبت امتیاز و نظر مشتریان"),
            ],
            "stats": [("۱۴۰", "صندلی"), ("۵۰+", "آیتم منو"), ("۴.۸/۵", "امتیاز مشتریان"), ("۳۰ دقیقه", "زمان آماده‌سازی")],
            "products": [
                ("چلوکباب کوبیده مخصوص", "۲۸۵,۰۰۰", "", "#fde9e7"),
                ("قورمه‌سبزی با گوشت قلعه‌نویی", "۲۴۰,۰۰۰", "", "#e9f7ec"),
                ("پاستا آلفردو با مرغ", "۲۲۰,۰۰۰", "", "#fdf3e3"),
                ("سالاد سزار", "۱۴۵,۰۰۰", "", "#eef7ee"),
                ("پیتزا مخصوص رستوران", "۳۱۰,۰۰۰", "", "#fdeceb"),
                ("دسر و نوشیدنی", "۹۵,۰۰۰", "", "#f3f0fb"),
            ],
            "about": f"{brand} با مواد اولیه‌ی تازه و فضای دلنشین، تجربه‌ای متفاوت از غذا خوردن می‌سازد.",
            "testimonials": [
                "کیفیت غذا عالی و رزرو آنلاین خیلی راحت بود.", "سپهر ع.",
                "برخورد پرسنل و فضای رستوران فوق‌العاده است.", "نرگس ک.",
            ],
            "quote_items": ["منوی آنلاین", "رزرو میز", "سفارش آنلاین", "نقشه و مسیریابی"],
        },
        "realestate": {
            "tagline": "خانه‌ی بعدی شما اینجاست",
            "nav": ["خانه", "املاک", "فروش", "اجاره", "مشاوران", "تماس"],
            "hero_t": f"{brand}؛ جستجوی هوشمند ملک با فیلتر دقیق",
            "hero_d": "جستجو بر اساس محله، متراژ، بودجه و سن بنا؛ ثبت آگهی و ارتباط مستقیم با مشاور.",
            "cta1": "جستجوی ملک", "cta2": "ثبت آگهی",
            "services": [
                ("🏠", "جستجوی پیشرفته", "فیلتر بر اساس قیمت، متراژ، محله و امکانات"),
                ("📷", "گالری تصاویر", "تصاویر باکیفیت و تور مجازی"),
                ("📝", "ثبت آگهی", "ثبت و مدیریت آگهی توسط مالک"),
                ("🧑‍💼", "مشاوران", "معرفی مشاور و شماره تماس مستقیم"),
                ("📊", "قیمت منطقه", "نمایش میانگین قیمت هر محله"),
                ("🔔", "هشدار ملک", "اطلاع‌رسانی ملک‌های جدید مطابق جستجو"),
            ],
            "stats": [("۴,۲۰۰+", "ملک فعال"), ("۱۸۰", "مشاور"), ("۲۴ ساعت", "تایید آگهی"), ("۹۴٪", "رضایت")],
            "products": [
                ("آپارتمان ۱۲۰ متری، نوساز، ۲ خواب", "۸,۴۰۰,۰۰۰,۰۰۰", "", "#e8f1ff"),
                ("ویلا ۳۵۰ متری با استخر", "۲۷,۵۰۰,۰۰۰,۰۰۰", "", "#e7f6ef"),
                ("دفتر اداری ۹۰ متری", "۱۲,۰۰۰,۰۰۰,۰۰۰", "", "#f4efff"),
                ("زمین ۵۰۰ متری مسکونی", "۱۹,۰۰۰,۰۰۰,۰۰۰", "", "#fdf0e7"),
                ("آپارتمان ۷۵ متری، اجاره", "۲۷,۰۰۰,۰۰۰", "", "#eef7fb"),
                ("مغازه ۴۰ متری تجاری", "۶,۳۰۰,۰۰۰,۰۰۰", "", "#f7f2ff"),
            ],
            "about": f"{brand} با شبکه‌ای از مشاوران حرفه‌ای، خرید و فروش و اجاره‌ی ملک را شفاف و سریع انجام می‌دهد.",
            "testimonials": [
                "ملک مناسب را خیلی سریع پیدا کردم.", "فرهاد م.",
                "فرایند ثبت آگهی ساده و دقیق بود.", "مینا ص.",
            ],
            "quote_items": ["جستجوی پیشرفته", "گالری و تور مجازی", "ثبت آگهی", "هشدار ملک جدید"],
        },
        "education": {
            "tagline": "یادگیری، مسیر رشد",
            "nav": ["خانه", "دوره‌ها", "اساتید", "وبلاگ", "درباره ما", "تماس"],
            "hero_t": f"{brand}؛ سامانه‌ی آموزش آنلاین با پنل دانشجو",
            "hero_d": "معرفی دوره‌ها، ثبت‌نام آنلاین، پنل دانشجو برای مشاهده‌ی ویدئوها و آزمون، و صدور گواهی پایان دوره.",
            "cta1": "مشاهده‌ی دوره‌ها", "cta2": "ثبت‌نام آنلاین",
            "services": [
                ("🎓", "دوره‌ها", "دسته‌بندی موضوعی با سطح‌بندی مقدماتی تا پیشرفته"),
                ("🎥", "پخش ویدئو", "پخش درس‌ها با پیشرفت‌یادگیری"),
                ("📝", "آزمون آنلاین", "آزمون با نمره‌دهی خودکار"),
                ("🏅", "گواهی پایان دوره", "صدور گواهی با شناسه‌ی یکتا"),
                ("👨‍🏫", "اساتید", "معرفی مدرسان و سوابق"),
                ("💬", "پشتیبانی", "گفتگو و رفع اشکال آنلاین"),
            ],
            "stats": [("۱۲۰+", "دوره"), ("۱۵,۰۰۰", "دانشجو"), ("۴.۷/۵", "رضایت"), ("۹۸٪", "نرخ تکمیل")],
            "products": [
                ("دوره‌ی جامع پایتون", "۲,۴۰۰,۰۰۰", "۲,۹۰۰,۰۰۰", "#eef2ff"),
                ("آموزش طراحی رابط کاربری", "۳,۲۰۰,۰۰۰", "۳,۸۰۰,۰۰۰", "#f3ecff"),
                ("دوره‌ی تحلیل داده", "۲,۸۰۰,۰۰۰", "۳,۳۰۰,۰۰۰", "#e9f7f2"),
                ("آموزش هوش مصنوعی کاربردی", "۴,۵۰۰,۰۰۰", "۵,۲۰۰,۰۰۰", "#fff3e8"),
                ("دوره‌ی بازاریابی دیجیتال", "۱,۹۰۰,۰۰۰", "۲,۳۰۰,۰۰۰", "#fdf0f5"),
                ("کارگاه مهارت‌های نرم", "۹۵۰,۰۰۰", "۱,۲۰۰,۰۰۰", "#f4f7fc"),
            ],
            "about": f"{brand} با بهره‌گیری از مدرسان باتجربه، مسیر یادگیری را کوتاه و لذت‌بخش می‌کند.",
            "testimonials": [
                "کیفیت آموزش عالی و پشتیبانی پاسخ‌گو.", "دانشجو",
                "گواهی دوره خیلی زود صادر شد.", "فراگیر",
            ],
            "quote_items": ["معرفی دوره‌ها", "ثبت‌نام آنلاین", "پنل دانشجو", "صدور گواهی"],
        },
    }
    en = {
        "tagline": "Professional, fast, reliable",
        "nav": ["Home", "Services", "Projects", "About", "Contact"],
        "hero_t": f"{brand} — a modern website built for growth",
        "hero_d": "This bilingual preview shows the English version of your website: same design, translated content, and a language switcher in the header.",
        "cta1": "Get in touch", "cta2": "View services",
    }
    data = dict(fa[archetype])
    data["en"] = en
    return data


# ---------------------------------------------------------------------------
# ابزارهای رندر
# ---------------------------------------------------------------------------
def _svg_hero(gradient: str, label: str) -> str:
    return f"""
<svg viewBox="0 0 520 360" style="width:100%;height:auto">
  <defs><linearGradient id="hg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity=".28"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient></defs>
  <rect x="10" y="14" width="500" height="330" rx="22" fill="url(#hg)"/>
  <rect x="48" y="52" width="424" height="150" rx="16" fill="#ffffff" opacity=".92"/>
  <rect x="70" y="76" width="120" height="12" rx="6" fill="{gradient}" opacity=".5"/>
  <rect x="70" y="100" width="220" height="10" rx="5" fill="#c7d0e6"/>
  <rect x="70" y="122" width="170" height="10" rx="5" fill="#dbe1ee"/>
  <rect x="330" y="86" width="112" height="82" rx="12" fill="{gradient}" opacity=".22"/>
  <rect x="48" y="222" width="130" height="104" rx="14" fill="#ffffff" opacity=".9"/>
  <rect x="192" y="222" width="130" height="104" rx="14" fill="#ffffff" opacity=".75"/>
  <rect x="336" y="222" width="130" height="104" rx="14" fill="#ffffff" opacity=".6"/>
  <text x="260" y="352" text-anchor="middle" font-size="13" fill="#ffffff" opacity=".85"
        font-family="Tahoma,sans-serif">{label}</text>
</svg>"""


def _svg_thumb(color: str, icon: str) -> str:
    return f"""
<svg viewBox="0 0 200 150" style="width:100%;height:150px">
  <rect width="200" height="150" fill="{color}"/>
  <circle cx="100" cy="66" r="34" fill="#ffffff" opacity=".55"/>
  <text x="100" y="80" text-anchor="middle" font-size="30">{icon}</text>
  <rect x="34" y="112" width="132" height="10" rx="5" fill="#ffffff" opacity=".7"/>
</svg>"""


def _services_html(items: list[tuple], lang: str = "fa") -> str:
    out = []
    for icon, title, desc in items:
        out.append(
            f'<div class="card2"><div class="ic">{icon}</div>'
            f'<div class="t">{title}</div><div class="d">{desc}</div></div>'
        )
    return f'<div class="grid g3">{"".join(out)}</div>'


def _stats_html(stats: list[tuple]) -> str:
    out = "".join(f'<div class="stat"><div class="v">{v}</div><div class="k">{k}</div></div>' for v, k in stats)
    return f'<div class="stats">{out}</div>'


def _products_html(products: list[tuple], icon: str = "🛍️") -> str:
    if not products:
        return ""
    out = []
    for item in products:
        name, price, old, color = item
        old_html = f'<span class="old">{old}</span>' if old else ""
        out.append(
            f'<div class="prod"><div class="ph">{_svg_thumb(color, icon)}</div>'
            f'<div class="bd"><div class="n">{name}</div>'
            f'<div class="pr">{old_html}{price} <span style="font-size:11px;font-weight:400">تومان</span></div></div></div>'
        )
    return f'<div class="grid g3" style="grid-template-columns:repeat(auto-fit,minmax(210px,1fr))">{"".join(out)}</div>'


# ---------------------------------------------------------------------------
# کتابخانه‌ی کامپوننت (Hero، قیمت، سؤالات متداول، گام‌ها، CTA، نشان اعتماد)
# ---------------------------------------------------------------------------
def _hero_html(c: dict, style, palette) -> str:
    """سه الگوی Hero بر اساس سبک انتخاب‌شده."""
    art = _svg_hero(palette.primary, "طراحی پیشنهادی صفحه‌ی اصلی")
    facts = "".join(
        f"<span class=\"chip\" style=\"background:rgba(255,255,255,.18);border-color:rgba(255,255,255,.3);"
        f"color:#fff\">{t}</span>" for t in ["✓ واکنش‌گرا", "✓ سریع", "✓ سئو پایه"])
    tagline = f"<div class=\"chip\" style=\"background:rgba(255,255,255,.18);border-color:rgba(255,255,255,.3);color:#fff\">{c['tagline']}</div>"
    ctas = (f"<div class=\"cta\"><span class=\"btn\">{c['cta1']}</span>"
            f"<span class=\"btn ghost\">{c['cta2']}</span></div>")

    if style.hero == "centered":
        return f"""
<div class="hero" style="background:{palette.gradient}"><div class="in" style="grid-template-columns:1fr;text-align:center">
  <div>
    {tagline}
    <h1 style="margin-top:14px;font-size:34px">{c['hero_t']}</h1>
    <p style="max-width:720px;margin:0 auto 20px">{c['hero_d']}</p>
    <div class="cta" style="justify-content:center"><span class="btn">{c['cta1']}</span><span class="btn ghost">{c['cta2']}</span></div>
    <div style="margin-top:14px">{facts}</div>
  </div>
</div></div>"""

    if style.hero == "image-left":
        return f"""
<div class="hero" style="background:{palette.gradient}"><div class="in" style="grid-template-columns:.9fr 1.1fr">
  <div>{art}</div>
  <div>
    {tagline}
    <h1 style="margin-top:14px">{c['hero_t']}</h1>
    <p>{c['hero_d']}</p>
    {ctas}
    <div style="margin-top:14px">{facts}</div>
  </div>
</div></div>"""

    return f"""
<div class="hero" style="background:{palette.gradient}"><div class="in">
  <div>
    {tagline}
    <h1 style="margin-top:14px">{c['hero_t']}</h1>
    <p>{c['hero_d']}</p>
    {ctas}
    <div style="margin-top:14px">{facts}</div>
  </div>
  <div>{art}</div>
</div></div>"""


def _process_html() -> str:
    steps = ["نیازسنجی و جمع‌آوری نیازها", "تایید طرح گرافیکی", "اجرا و بارگذاری محتوا",
             "آموزش، تست و تحویل"]
    out = "".join(
        f"<div class=\"card2\" style=\"text-align:center\"><div class=\"ic\" style=\"margin:0 auto 8px\">{i}</div>"
        f"<div class=\"t\">{t}</div></div>" for i, t in enumerate(steps, 1))
    return ("<div class=\"sect alt\"><div class=\"wrap\"><h2>مسیر همکاری</h2>"
            "<div class=\"sub\">از امروز تا تحویل</div>"
            f"<div class=\"grid g4\">{out}</div></div></div>")


def _pricing_html(brand: str) -> str:
    plans = [("پایه", "برای شروع", "صفحه‌ی اصلی + فرم تماس"),
             ("حرفه‌ای", "پرفروش‌ترین", "چند صفحه + پنل مدیریت"),
             ("سازمانی", "برای رشد", "صفحات بیشتر + سئو")]
    out = []
    for name, tag, desc in plans:
        out.append(
            "<div class=\"card2\" style=\"text-align:center\">"
            f"<div class=\"muted\">{tag}</div><h3 style=\"margin:6px 0\">{name}</h3>"
            "<div style=\"font-size:21px;font-weight:800;color:var(--p)\">توافقی</div>"
            f"<div class=\"d muted\" style=\"margin:8px 0 12px\">{desc}</div>"
            "<span class=\"btn ghost\">انتخاب بسته</span></div>")
    return ("<div class=\"sect\"><div class=\"wrap\">"
            f"<h2>بسته‌های پیشنهادی {brand}</h2>"
            "<div class=\"sub\">قیمت نهایی همان مبلغی است که در پیشنهاد ارسالی می‌بینید</div>"
            f"<div class=\"grid g3\">{''.join(out)}</div></div></div>")


def _faq_html() -> str:
    rows = [("چه مدت طول می‌کشد؟", "زمان تحویل دقیق در همین صفحه و در پیشنهاد ارسالی نوشته شده است."),
            ("امکان تغییر بعد از تحویل دارم؟", "بله؛ یک دور بازنگری رایگان پس از تحویل در نظر گرفته می‌شود."),
            ("روی موبایل هم درست کار می‌کند؟", "بله؛ طراحی کاملاً واکنش‌گرا است و روی موبایل تست می‌شود."),
            ("پشتیبانی بعد از تحویل چطور است؟", "رفع اشکال و آموزش کار با پنل پس از تحویل ارائه می‌شود.")]
    out = "".join(f"<div class=\"card2\" style=\"margin-bottom:10px\"><div class=\"t\">❓ {q}</div>"
                  f"<div class=\"d\">{a}</div></div>" for q, a in rows)
    return ("<div class=\"sect alt\"><div class=\"wrap\" style=\"max-width:820px\">"
            f"<h2>سؤالات متداول</h2>{out}</div></div>")


def _cta_band_html(c: dict) -> str:
    return ("<div class=\"sect\" style=\"padding:30px 18px\"><div class=\"wrap\">"
            "<div style=\"background:var(--grad);color:#fff;border-radius:22px;padding:30px 24px;text-align:center\">"
            "<h2 style=\"color:#fff;margin-bottom:6px\">آماده‌ی شروع هستید؟</h2>"
            f"<p style=\"opacity:.92;margin:0 0 16px\">{c['tagline']} — همین امروز پیام بدهید تا زمان‌بندی قطعی شود.</p>"
            f"<span class=\"btn\" style=\"background:#fff;color:var(--ink)\">{c['cta1']}</span>"
            "</div></div></div>")


def _mock_page(c: dict, archetype: str, style, bilingual: bool) -> str:
    palette = ds.palette_of(style)
    primary, accent, gradient = palette.primary, palette.accent, palette.gradient
    nav = "".join(f"<span>{n}</span>" for n in c["nav"])
    en = c.get("en") or {}
    hero_en = ""
    if bilingual:
        hero_en = f"""
<div class="sect alt" style="padding:22px 18px" id="en-block">
  <div style="max-width:760px;margin:0 auto;text-align:center">
    <div class="chip">English version — همان طراحی با محتوای انگلیسی</div>
    <h2 style="margin-top:12px">{en.get('hero_t','')}</h2>
    <p class="muted">{en.get('hero_d','')}</p>
    <div class="hero" style="margin-top:14px;border-radius:16px;padding:26px 18px">
      <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap">
        <span class="btn alt">{en.get('cta1','')}</span><span class="btn ghost">{en.get('cta2','')}</span>
      </div>
    </div>
  </div>
</div>"""
    services_en = ""
    if bilingual:
        services_en = f"""
<div class="sect" style="padding-top:0">
  <div style="max-width:760px;margin:0 auto" dir="ltr">
    <h2 style="text-align:center">Services</h2>
    <div class="grid g3">
      <div class="card2"><div class="t">Search &amp; filter</div><div class="d">Fast product discovery</div></div>
      <div class="card2"><div class="t">Cart &amp; checkout</div><div class="d">Smooth payment flow</div></div>
      <div class="card2"><div class="t">Order tracking</div><div class="d">Live status for customers</div></div>
    </div>
  </div>
</div>"""
    products_block = _products_html(c.get("products") or [], "🛍️")
    products_section = (
        f'<div class="sect alt"><div class="wrap"><h2>نمونه محصولات / خروجی‌های قابل ارائه</h2>'
        f'<div class="sub">طراحی کارت محصول با تصویر، قیمت و دکمه‌ی افزودن به سبد</div>'
        f'{products_block}</div></div>'
        if products_block else ""
    )
    t = c["testimonials"]
    quotes = []
    for i in range(0, len(t), 2):
        quotes.append(
            f'<div class="quote"><div class="txt">«{t[i]}»</div>'
            f'<div class="who"><div class="av"></div><div><b>{t[i+1]}</b><div class="muted">مشتری نمونه</div></div></div></div>'
        )
    return f"""
<div class="mockwin">
  <div class="dots"><i></i><i></i><i></i><span class="muted" style="margin-right:8px;font-size:11.5px">
  پیش‌نمایش ظاهری — {ARCHETYPE_LABELS[archetype]} · سبک: {style.label}</span></div>

  <div class="mh"><div class="in">
    <div class="logo"><span class="m">{clean_text(c['brand'])[:1] or 'F'}</span>{c['brand']}</div>
    <div class="nav">{nav}</div>
    <div><span class="btn" style="padding:8px 16px;font-size:13px">{c['cta1']}</span></div>
  </div></div>

  {_hero_html(c, style, palette)}

  <div class="sect"><div class="wrap">
    <h2>امکاناتی که در این سایت پیاده‌سازی می‌شود</h2>
    <div class="sub">هر بخش در نسخه‌ی نهایی به‌طور کامل و قابل استفاده تحویل می‌گردد</div>
    {_services_html(c['services'])}
  </div></div>

  <div class="sect alt"><div class="wrap">{_stats_html(c['stats'])}</div></div>

  {products_section}

  {_process_html()}
  {_pricing_html(c['brand'])}

  <div class="sect"><div class="wrap">
    <h2>درباره‌ی مجموعه</h2>
    <div class="sub" style="text-align:right;max-width:820px;margin:0 auto 18px">{c['about']}</div>
    <div class="grid g3" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr))">
      {''.join(f'<div class="card2" style="text-align:center"><div class="ic" style="margin:0 auto 8px">✓</div><div class="t">{q}</div></div>' for q in c['quote_items'])}
    </div>
  </div></div>

  <div class="sect alt"><div class="wrap">
    <h2>نظر کاربران</h2><div class="sub">نمونه بازخورد پس از راه‌اندازی</div>
    <div class="grid g3" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">{''.join(quotes)}</div>
  </div></div>

  {hero_en}{services_en}

  {_faq_html()}

  <div class="sect"><div class="wrap">
    <h2>تماس با ما</h2><div class="sub">فرم درخواست و اطلاعات تماس</div>
    <div class="grid" style="grid-template-columns:1.2fr .8fr">
      <div class="quote">
        <div class="formrow">
          <div class="field"><label>نام و نام خانوادگی</label><input placeholder="مثال: علی محمدی"></div>
          <div class="field"><label>شماره تماس</label><input placeholder="09xxxxxxxxx"></div>
        </div>
        <div class="field"><label>موضوع درخواست</label>
          <select><option>درخواست مشاوره</option><option>استعلام قیمت</option><option>همکاری</option></select></div>
        <div class="field"><label>توضیحات</label><textarea rows="4" placeholder="متن پیام شما…"></textarea></div>
        <span class="btn">ارسال درخواست</span>
      </div>
      <div>
        <div class="card2"><div class="t">📞 تلفن</div><div class="d">۰۲۱-۱۲۳۴۵۶۷۸</div></div>
        <div class="card2" style="margin-top:12px"><div class="t">✉️ ایمیل</div><div class="d">info@example.com</div></div>
        <div class="card2" style="margin-top:12px"><div class="t">📍 آدرس</div><div class="d">تهران، خیابان نمونه، پلاک ۱۲</div></div>
        <div class="card2" style="margin-top:12px"><div class="t">🕘 ساعات کاری</div><div class="d">شنبه تا چهارشنبه ۹ تا ۱۸</div></div>
      </div>
    </div>
  </div></div>

  {_cta_band_html(c)}

  <div class="mfoot"><div class="wrap"><div class="cols">
    <div><h4>{c['brand']}</h4><p>{c['tagline']}</p></div>
    <div><h4>دسترسی سریع</h4>{''.join(f'<div>{n}</div>' for n in c['nav'])}</div>
    <div><h4>خدمات</h4>{''.join(f'<div>{s[1]}</div>' for s in c['services'][:4])}</div>
    <div><h4>تماس</h4><div>info@example.com</div><div>۰۲۱-۱۲۳۴۵۶۷۸</div></div>
  </div>
  <div class="bt">طرح پیشنهادی — نمونه‌ی گرافیکی؛ نسخه‌ی نهایی پس از تایید قرارداد تحویل می‌شود</div>
  </div></div>
</div>"""


# ---------------------------------------------------------------------------
# رندرِ صفحات اپلیکیشن / داشبورد / pipeline / ربات
# ---------------------------------------------------------------------------
def _screen_shell(title: str, sidebar: list[str], body: str, extra: str = "") -> str:
    return f"""
<div class="mockwin">
  <div class="dots"><i></i><i></i><i></i><span class="muted" style="margin-right:8px;font-size:11.5px">
  پیش‌نمایش صفحات — {title}</span></div>
  <div style="display:grid;grid-template-columns:210px 1fr;min-height:430px">
    <div style="background:#0f1730;color:#aab6d8;padding:16px 14px;font-size:13.5px">
      <div style="color:#fff;font-weight:800;margin-bottom:14px">📊 پنل مدیریت</div>
      {''.join(f'<div style="padding:7px 10px;border-radius:9px;margin-bottom:4px{";background:#1c2947;color:#fff" if i == 0 else ""}">{s}</div>' for i, s in enumerate(sidebar))}
    </div>
    <div style="padding:16px">{body}</div>
  </div>
</div>
{extra}"""


def _bars(values: list[int], labels: list[str]) -> str:
    mx = max(values) or 1
    out = []
    for v, lab in zip(values, labels):
        h = int(150 * v / mx)
        out.append(
            f'<div style="text-align:center"><div style="height:{h}px" class="bar"></div>'
            f'<div class="muted" style="font-size:11px;margin-top:6px">{lab}</div></div>'
        )
    return f'<div style="display:flex;align-items:end;gap:10px;height:180px;padding:10px 6px;border-bottom:1px solid #eceff7">{"".join(out)}</div>'


def _app_screens(project: Project, screening: dict) -> str:
    """صفحات واقعی یک اپ/داشبورد را به‌صورت گرافیکی نشان می‌دهد."""
    features = screening.get("features") or []
    rows = "".join(
        f"<tr><td>{i+1:02d}</td><td>{(f or 'نیازمندی پروژه')[:64]}</td>"
        f"<td><span class='badge b-run'>در حال اجرا</span></td><td>{80 + (i * 3) % 18}٪</td></tr>"
        for i, f in enumerate(features[:8])
    ) or "<tr><td>۱</td><td>نیازمندی‌های پروژه از متن آگهی استخراج می‌شود</td><td><span class='badge b-run'>در حال اجرا</span></td><td>۰٪</td></tr>"
    kpis = "".join(
        f'<div class="kpi"><div class="k">{k}</div><div class="v">{v}</div><div class="d">{d}</div></div>'
        for k, v, d in [("کاربران فعال", "۱,۲۴۸", "↑ ۱۲٪ این هفته"),
                        ("درخواست‌های امروز", "۳۴۲", "↑ ۸٪"),
                        ("زمان پاسخ", "۱.۲ ثانیه", "↓ بهتر شده"),
                        ("نرخ موفقیت", "۹۶٪", "پایدار")]
    )
    body = f"""
<div class="grid g4" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:14px">{kpis}</div>
<div class="card2" style="margin-bottom:14px"><div class="t" style="margin-bottom:8px">روند عملکرد ۳۰ روز اخیر</div>
{_bars([12, 18, 9, 24, 30, 22, 35, 28, 41, 38, 46, 52], ['۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹', '۱۰', '۱۱', '۱۲'])}
</div>
<div class="card2"><div class="t" style="margin-bottom:8px">آخرین فعالیت‌ها</div>
<table><thead><tr><th>#</th><th>مورد</th><th>وضعیت</th><th>پیشرفت</th></tr></thead><tbody>{rows}</tbody></table></div>
"""
    return _screen_shell("داشبورد و صفحات مدیریت",
                         ["داشبورد", "پروژه‌ها", "درخواست‌ها", "کاربران", "گزارش‌ها", "تنظیمات"],
                         body)


def _pipeline_screens(project: Project, screening: dict) -> str:
    files = _pipeline_rows(project)
    rows = "".join(
        f"<tr><td>{f['name']}</td><td>{f['pages']}</td><td>{f['tables']}</td><td>{f['formulas']}</td>"
        f"<td>{f['images']}</td><td><span class='badge b-ok'>{f['acc']}٪ دقت</span></td></tr>"
        for f in files[:6]
    )
    sample = json.dumps({
        "file": files[0]["name"] if files else "book-01.pdf",
        "pages": files[0]["pages"] if files else 320,
        "chapters": [{"title": "فصل اول", "paragraphs": 42, "tables": 3, "formulas": 7}],
        "output_format": "json",
        "assets": {"images": 24, "extracted_at": "2026-09-28T09:00:00Z"},
    }, ensure_ascii=False, indent=2)
    body = f"""
<div class="grid g4" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:14px">
  <div class="kpi"><div class="k">فایل‌های پردازش‌شده</div><div class="v">۱۵۰</div><div class="d">از ۱۵۰ کتاب</div></div>
  <div class="kpi"><div class="k">دقت استخراج</div><div class="v">۹۷٪</div><div class="d">کنترل کیفیت خودکار</div></div>
  <div class="kpi"><div class="k">زمان هر کتاب</div><div class="v">۴۵ ثانیه</div><div class="d">بدون دخالت دستی</div></div>
  <div class="kpi"><div class="k">خروجی</div><div class="v">JSON</div><div class="d">ساختاریافته و قابل جستجو</div></div>
</div>
<div class="card2" style="margin-bottom:14px">
  <div class="rowflex" style="justify-content:space-between;margin-bottom:10px">
    <div class="t">صف پردازش</div><span class="btn" style="padding:7px 14px;font-size:13px">شروع استخراج</span></div>
  <div class="progress"><i style="width:72%"></i></div>
  <div class="log">› خواندن فایل و تشخیص ساختار
› استخراج متن و حفظ ترتیب پاراگراف‌ها
› استخراج جداول و تبدیل به JSON
› شناسایی و ذخیره فرمول‌ها
› کنترل کیفیت و تولید گزارش</div>
</div>
<div class="card2" style="margin-bottom:14px"><div class="t" style="margin-bottom:8px">نتایج پردازش</div>
<table><thead><tr><th>فایل</th><th>صفحات</th><th>جداول</th><th>فرمول‌ها</th><th>تصاویر</th><th>کیفیت</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<div class="card2"><div class="t" style="margin-bottom:8px">نمونه خروجی JSON</div><pre class="json" style="margin:0">{sample}</pre></div>
"""
    return _screen_shell("پنل پردازش و خروجی ساختاریافته",
                         ["داشبورد", "بارگذاری فایل", "صف پردازش", "خروجی‌ها", "گزارش کیفیت", "تنظیمات"],
                         body)


def _bot_screens(project: Project, screening: dict) -> str:
    chat = "".join(
        f'<div class="msg {"me" if i % 2 else "you"}" style="background:{"#3b5bdb;color:#fff;margin-left:auto" if i % 2 else "#fff;border:1px solid #e2e7f2"};'
        f'padding:8px 12px;border-radius:14px;margin:6px 0;max-width:78%;font-size:13.5px">{m}</div>'
        for i, m in enumerate([
            "سلام! من دستیار هوشمند شما هستم 👋",
            "چطور می‌توانم کمک کنم؟",
            "قیمت محصول X چند است؟",
            "قیمت محصول X برابر ۱۲۵,۰۰۰ تومان است. موجودی: ۱۴ عدد",
        ])
    )
    body = f"""
<div class="grid" style="grid-template-columns:1fr 1fr;gap:14px">
  <div class="card2"><div class="t" style="margin-bottom:10px">گفتگو با ربات</div>
    <div style="background:#eef1f8;border-radius:12px;padding:10px">{chat}</div>
    <div class="rowflex" style="margin-top:10px"><input placeholder="پیام خود را بنویسید…"><span class="btn">ارسال</span></div>
  </div>
  <div class="card2"><div class="t" style="margin-bottom:10px">پنل مدیریت ربات</div>
    <div class="grid g4" style="grid-template-columns:1fr 1fr">
      <div class="kpi"><div class="k">کاربران فعال</div><div class="v">۱,۲۴۸</div><div class="d">↑ ۱۲٪</div></div>
      <div class="kpi"><div class="k">پیام امروز</div><div class="v">۳۴۲</div><div class="d">پاسخ ۱.۲ ثانیه</div></div>
      <div class="kpi"><div class="k">دستورات</div><div class="v">۱۸</div><div class="d">قابل افزودن</div></div>
      <div class="kpi"><div class="k">رضایت</div><div class="v">۴.۸/۵</div><div class="d">از نظرسنجی</div></div>
    </div>
    <table style="margin-top:12px"><thead><tr><th>دستور</th><th>پاسخ</th><th>تعداد استفاده</th></tr></thead>
      <tbody><tr><td>قیمت</td><td>ارسال لیست قیمت</td><td>۱,۲۰۴</td></tr>
      <tr><td>پیگیری</td><td>وضعیت سفارش</td><td>۸۷۰</td></tr>
      <tr><td>پشتیبانی</td><td>اتصال به اپراتور</td><td>۳۱۵</td></tr></tbody></table>
  </div>
</div>
"""
    return _screen_shell("ربات و پنل مدیریت", ["داشبورد", "گفتگوها", "کاربران", "دستورات", "گزارش‌ها", "تنظیمات"], body)


def _pipeline_rows(project: Project) -> list[dict]:
    names = ["کتاب-جلد-اول.pdf", "کتاب-جلد-دوم.pdf", "کتاب-جلد-سوم.pdf", "مرجع-تخصصی.pdf", "مجموعه-مقالات.pdf"]
    out = []
    for i, n in enumerate(names):
        out.append({
            "name": n, "size": f"{2 + i * 3}.{i + 2} MB", "pages": 180 + i * 40,
            "tables": 6 + i * 3, "formulas": 12 + i * 7, "images": 20 + i * 9,
            "status": "آماده", "badge": "b-ok", "acc": 96 - i,
        })
    return out


# ---------------------------------------------------------------------------
# خروجی نهایی
# ---------------------------------------------------------------------------
def _doc(title: str, subtitle: str, chips: list[str], style, body: str,
         watermark: str, ribbon_note: str = "") -> str:
    palette = ds.palette_of(style)
    primary, accent = palette.primary, palette.accent
    chip_html = "".join(f'<span class="chip">{c}</span>' for c in chips)
    wm = _watermark_svg(watermark)
    design_css = ds.css_tokens(style) + "\n" + ds.css_style(style)
    return f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{title}</title>
<style>{design_css}{CSS}{CSS_MOCK}{CSS_LOCK}</style></head>
<body>
{LOCK_HTML.replace("{wm}", wm)}
<div class="mockbar">👁 <b>پیش‌نمایش گرافیکیِ نمونه</b> — این طرح برای نمایشِ خروجی پروژه ساخته شده و
هیچ بخش آن قابل استفاده نیست{ribbon_note}</div>
<div style="padding:16px 0 40px">
<div class="wrap" style="max-width:1160px">
  <div style="margin-bottom:14px">
    <h1 style="font-size:22px;margin:0 0 6px">{title}</h1>
    <div class="muted">{subtitle}</div>
    <div style="margin-top:8px">{chip_html}</div>
  </div>
  {body}
</div>
</div>
<script>{LOCK_JS}</script>
</body></html>"""


def _spec_block(screening: dict, proposal: dict | None) -> str:
    deliverables = screening.get("deliverables") or []
    milestones = (proposal or {}).get("milestones") or []
    d_html = "".join(f'<div class="card2"><div class="t">✓ {d}</div></div>' for d in deliverables) or \
             '<div class="muted">موارد تحویل از متن آگهی استخراج می‌شود.</div>'
    m_html = "".join(
        f'<div class="step"><span class="t">{m["title"]}</span> — {int(m["share"] * 100)}٪'
        f'<div class="muted">{m["when"]}</div></div>' for m in milestones
    )
    return f"""
<div class="card" style="margin-top:16px"><h2>چه چیزی تحویل می‌گیرید</h2>
<div class="grid g3">{d_html}</div>
{'<h2 style="margin-top:18px">برنامه‌ی تحویل و پرداخت</h2><div class="steps">' + m_html + '</div>' if m_html else ''}
</div>"""


def choose_kind(screening: dict, project: Project) -> str:
    cat = screening.get("category", "other")
    hay = f"{project.title} {project.description}".lower()
    # نرم‌افزار/سامانه/اپلیکیشن → صفحات اپلیکیشن
    if re.search(r"اپلیکیشن|اپ موبایل|نرم ?افزار|سامانه|پورتال|پنل کاربر", hay):
        return "app"
    # ERP / یکپارچه‌سازی / داشبورد → صفحات داشبورد
    if re.search(r"odoo|erp|یک ?پارچه ?سازی|انبار|حسابداری|داشبورد|رهگیری سفارش", hay):
        return "dashboard"
    if cat in ("data_pipeline", "automation", "data_entry"):
        return "pipeline"
    if cat == "bot":
        return "bot"
    if cat == "dashboard":
        return "dashboard"
    if cat in ("landing", "web_app", "plugin_cms", "mobile_app", "chrome_extension", "content"):
        return "site"
    if re.search(r"odoo|erp|یکپارچه ?سازی|انبار|حسابداری", hay):
        return "dashboard"
    return "site"


def build_demo(project: Project, screening: dict, proposal: dict | None, out_dir: Path,
               base_url: str = "", style_override: str = "") -> dict:
    """دو فایل می‌سازد: index.html (داخلی) و client.html (ارسال به کارفرما)."""
    kind = choose_kind(screening, project)
    archetype = detect_archetype(project, screening)
    brand = _brand_from_title(project.title, archetype)
    try:
        from .config import load_config as _load

        style_override_from_config = str(_load().raw.get("demo", {}).get("style", "auto") or "auto")
    except Exception:  # noqa: BLE001
        style_override_from_config = "auto"
    chosen = (style_override or style_override_from_config).strip().lower()
    style = ds.pick_style(project, archetype, "" if chosen in ("auto", "", "خودکار") else chosen)
    palette = ds.palette_of(style)
    bilingual = bool(re.search(r"انگلیسی|دو ?زبانه|چند ?زبانه|bilingual", project.title + project.description, re.I))
    c = _content(archetype, brand)
    c["brand"] = brand

    slug = slugify(f"{project.source}-{project.external_id}-{project.title}")
    folder = Path(out_dir) / slug
    folder.mkdir(parents=True, exist_ok=True)

    # --- بدنه‌ی اصلی (پیش‌نمایش گرافیکی) ---
    if kind == "site":
        mock = _mock_page(c, archetype, style, bilingual)
    elif kind == "pipeline":
        mock = _pipeline_screens(project, screening)
    elif kind == "bot":
        mock = _bot_screens(project, screening)
    else:
        mock = _app_screens(project, screening)

    # --- نسخه‌ی داخلی ---
    price = to_persian_digits(f'{proposal["price"]:,}') + " تومان" if proposal else "—"
    budget = to_persian_digits(f'{project.budget_toman:,}') + " تومان" if project.budget_toman else "اعلام نشده"
    internal_body = f"""
<div class="card"><h2>اطلاعات پروژه</h2>
<div class="grid g4">
  <div class="kpi"><div class="k">منبع</div><div class="v" style="font-size:16px">{project.source_label}</div></div>
  <div class="kpi"><div class="k">امتیاز اجراپذیری</div><div class="v">{to_persian_digits(screening['score'])}/۱۰۰</div></div>
  <div class="kpi"><div class="k">برآورد زمان</div><div class="v">{to_persian_digits(screening.get('est_hours', '—'))} ساعت</div></div>
  <div class="kpi"><div class="k">زمان تحویل</div><div class="v">{to_persian_digits(screening.get('schedule_days', '—'))} روز</div></div>
  <div class="kpi"><div class="k">قیمت پیشنهادی ما</div><div class="v" style="font-size:19px">{price}</div></div>
  <div class="kpi"><div class="k">بودجه کارفرما</div><div class="v" style="font-size:17px">{budget}</div></div>
</div>
<div class="muted" style="margin-top:12px">نوع پروژه شناسایی‌شده: <b>{ARCHETYPE_LABELS[archetype]}</b>
 · قالب دمو: <b>{kind}</b>{' · دو زبانه (فارسی/انگلیسی)' if bilingual else ''}</div>
<div class="muted">آگهی: <a href="{project.url}" target="_blank" rel="noopener">{clean_text(project.title)}</a></div>
</div>

{mock}
{_spec_block(screening, proposal)}

<div class="card"><h2>نسخه‌ی ارسال به کارفرما</h2>
<div class="muted">فایل <b>client.html</b> در همین پوشه، نسخه‌ای است که مستقیماً برای کارفرما ارسال می‌شود:
بدون امتیاز/برآورد داخلی، با واترمارک و قفلِ استفاده.</div>
<div style="margin-top:10px"><a class="go" href="client.html" target="_blank">باز کردن client.html ↗</a></div>
</div>
"""
    index = folder / "index.html"
    index.write_text(
        _doc(
            clean_text(project.title),
            f"پیش‌نمایش گرافیکی برای آگهی «{clean_text(project.title)}» — {ARCHETYPE_LABELS[archetype]}",
            [f"منبع: {project.source_label}", f"دسته: {screening['category_label']}",
             f"امتیاز: {to_persian_digits(screening['score'])}/۱۰۰", f"نوع پیش‌نمایش: {kind}",
             "نسخه‌ی داخلی"],
            style, internal_body, f"نمونه دمو — {brand}",
        ),
        encoding="utf-8",
    )

    # --- نسخه‌ی کارفرما (بدون اطلاعات داخلی) ---
    client_body = f"""
<div class="card"><h2>پیش‌نمایش اختصاصیِ طراحیِ پروژه‌ی شما</h2>
<div class="muted">این پیش‌نمایش بر اساس توضیحات آگهی شما طراحی شده تا پیش از شروع همکاری،
ظاهر و امکاناتِ خروجی نهایی را ببینید. نسخه‌ی کامل و قابل استفاده بلافاصله پس از تایید،
طبق زمان‌بندی زیر تحویل می‌شود.</div>
<div class="grid g4" style="margin-top:14px">
  <div class="kpi"><div class="k">مبلغ پیشنهادی</div><div class="v" style="font-size:19px">{price}</div></div>
  <div class="kpi"><div class="k">زمان تحویل</div><div class="v">{screening.get('schedule_days', '—')} روز کاری</div></div>
  <div class="kpi"><div class="k">تعداد صفحات</div><div class="v">{len(c['nav'])} بخش اصلی</div></div>
  <div class="kpi"><div class="k">طراحی</div><div class="v" style="font-size:17px">واکنش‌گرا (موبایل و دسکتاپ)</div></div>
</div>
</div>

{mock}
{_spec_block(screening, proposal)}

<div class="card"><h2>مرحله‌ی بعد</h2>
<div class="muted">برای شروع اجرا و دریافت نسخه‌ی قابل استفاده، کافی است از طریق همین آگهی پیام بدهید؛
پس از تایید، طراحی نهایی، پیاده‌سازی، بارگذاری روی هاست و آموزش کار با سایت را انجام می‌دهم.</div>
<div style="margin-top:12px"><span class="btn">درخواست شروع اجرا</span></div>
</div>
"""
    client = folder / "client.html"
    client.write_text(
        _doc(
            f"پیش‌نمایش طراحی — {brand}",
            "این یک پیش‌نمایش گرافیکیِ اختصاصی است؛ خروجی نهایی پس از تایید قرارداد تحویل می‌شود.",
            [ARCHETYPE_LABELS[archetype], "پیش‌نمایش اختصاصی", "غیرقابل استفاده (نمونه)"],
            style, client_body, f"پیش‌نمایش — نمونه غیرقابل استفاده",
        ),
        encoding="utf-8",
    )

    errors, warnings = ds.check_design(client.read_text(encoding="utf-8"), style, client_version=True)
    if errors:
        print(f"  ! هشدار کیفیت طراحی ({len(errors)}): {errors[0]}")
    for w in warnings[:2]:
        print(f"  · نکته‌ی طراحی: {w}")

    meta = {
        "project_id": project.id,
        "title": project.title,
        "source": project.source,
        "kind": kind,
        "style": style.key,
        "style_label": style.label,
        "palette": palette.key,
        "design_errors": errors,
        "design_warnings": warnings,
        "archetype": archetype,
        "archetype_label": ARCHETYPE_LABELS[archetype],
        "brand": brand,
        "bilingual": bilingual,
        "path": str(index),
        "rel": f"{slug}/index.html",
        "client_path": str(client),
        "client_rel": f"{slug}/client.html",
        "url": f"{base_url}/demos/{slug}/" if base_url else f"file://{index}",
        "built_at": datetime.now().isoformat(timespec="seconds"),
    }
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta
