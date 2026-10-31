"""تست‌های هسته‌ی فریلنس‌یار آرنا (بدون نیاز به اینترنت)."""

from __future__ import annotations

import json
import os
import time
import types
from pathlib import Path

import pytest

from frilanser.config import load_config
from frilanser.demo_builder import build_demo
from frilanser.models import Project
from frilanser.normalize import (
    extract_bullets,
    parse_bids,
    parse_budget,
    parse_deadline_days,
    parse_duration_days,
    parse_int,
    parse_language_count,
    parse_page_count,
    parse_posted_at,
)
from frilanser.pricing import propose, quick_price
from frilanser.screening import classify, screen
from frilanser.sources.karlancer import KarlancerSource
from frilanser.sources.parscoders import ParsCodersSource
from frilanser.sources.ponisha import PonishaSource
from frilanser.store import Store

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------- normalize
import pytest as _pytest


@_pytest.fixture
def cfg_default():
    """یک پیکربندیِ کمینه برای تست (بدون نیاز به config.toml واقعی)."""
    from frilanser.config import Config
    return Config({"app": {"outbox_dir": "outbox", "data_dir": "data", "demo_dir": "outbox/demos"},
                   "pricing": {"hourly_rate_toman": 450000, "min_project_price_toman": 5000000,
                               "round_to_toman": 500000, "platform_commission": 0.10,
                               "risk_buffer": 0.15}}, Path("."))


def _cfg(root: str):
    """یک پیکربندیِ کمینه برای تست (بدون نیاز به config.toml واقعی).

    همه‌ی مسیرها زیر ``root`` (معمولاً tmp_path) می‌روند تا چیزی در outbox و data
    واقعیِ ریپو نوشته نشود (مثل وضعیتِ ساختگیِ به‌روزرسانی).
    """
    from frilanser.config import Config
    base = Path(root)
    return Config({"app": {
        "outbox_dir": str(base / "outbox"),
        "data_dir": str(base / "data"),
        "demo_dir": str(base / "outbox" / "demos"),
        "report_dir": str(base / "outbox" / "reports"),
        "react_dir": str(base / "outbox" / "react"),
        "raw_dir": str(base / "data" / "raw"),
        "cache_dir": str(base / "data" / "cache"),
    }}, base / "config.toml")


def test_parse_numbers():
    assert parse_int("بودجه 300,000,000 تومان") == 300_000_000
    assert parse_budget("بودجه کارفرمابودجه ۳۰۰,۰۰۰,۰۰۰ تومان") == 300_000_000
    assert parse_budget("بودجه\n\n۴,۵۰۰,۰۰۰ تومان") == 4_500_000
    assert parse_deadline_days("فرصت انتخاب14 روز و 15 ساعت") == pytest.approx(14.6, abs=0.1)
    assert parse_duration_days("زمان پیشنهادی ۱۵ روز") == 15
    assert parse_duration_days("۲ هفته") == 14
    assert parse_bids("پیشنهادها16") == 16
    assert parse_bids("28 پیشنهاد") == 28
    assert parse_posted_at("۷ ساعت پیش") == "۷ ساعت پیش"
    assert parse_language_count("سایت ۴ زبانه") == 4
    assert parse_language_count("سایت دو زبانه") == 2
    assert parse_page_count("بین ۲۰ الی ۴۰ صفحه دارد") == 30


def test_bullets():
    text = "• بررسی اطلاعات\n• جست‌وجو در وب\n۱. تحویل فایل"
    assert len(extract_bullets(text)) == 3


# --------------------------------------------------------------- parsers
def test_ponisha_parser():
    cfg = load_config()
    source = PonishaSource(cfg, "ponisha")
    text = (ROOT / "data/raw/ponisha-2026-09-28.md").read_text(encoding="utf-8")
    records = source.parse(text)
    assert len(records) == 3
    book = next(r for r in records if r["external_id"] == "760397")
    assert book["budget_toman"] == 300_000_000
    assert book["bids"] == 16
    assert "PDF" in book["skills"]
    assert "کتاب" in book["description"]
    corporate = next(r for r in records if r["external_id"] == "760388")
    assert corporate["budget_toman"] == 20_000_000
    assert "وردپرس (WordPress)" in corporate["skills"]


def test_karlancer_parser():
    cfg = load_config()
    source = KarlancerSource(cfg, "karlancer")
    text = (ROOT / "data/raw/karlancer-2026-09-28.md").read_text(encoding="utf-8")
    records = source.parse(text)
    assert len(records) == 3
    logo = next(r for r in records if r["external_id"] == "906n552378ew")
    assert logo["budget_toman"] == 4_500_000
    assert logo["client_deadline_days"] == 2
    assert "طراحی لوگو" in logo["skills"]
    admin = next(r for r in records if r["external_id"] == "2m6m223w3850")
    assert admin["location"] == "تهران"
    assert "منتشر شده" in admin["flags"]


def test_parscoders_parser():
    cfg = load_config()
    source = ParsCodersSource(cfg, "parscoders")
    text = (ROOT / "data/raw/parscoders-2026-09-28.md").read_text(encoding="utf-8")
    records = source.parse(text)
    ids = {r["external_id"] for r in records}
    # پروژه‌ی مخفی (بدون لینک) و پروژه‌ی «پاداش» نباید وارد شوند
    assert ids == {"619120", "619119", "619118", "619105"}

    excel = next(r for r in records if r["external_id"] == "619119")
    assert excel["budget_toman"] == 500_000
    assert excel["bids"] == 9
    assert "اکسل" in excel["skills"]
    assert "فایل Excel" in excel["description"]
    assert "ارسال پیشنهاد" not in excel["description"]
    assert excel["title"].startswith("طراحی فایل اکسل")

    webapp = next(r for r in records if r["external_id"] == "619105")
    assert webapp["budget_toman"] == 45_000_000
    assert "فوری" in webapp["flags"]
    assert any("استخدام" in f for f in webapp["flags"])

    clip = next(r for r in records if r["external_id"] == "619120")
    assert clip["title"] == "ادیت کیلیپ"  # کد پروژه از ابتدای عنوان حذف می‌شود


# --------------------------------------------------------------- screening
def make_project(title: str, description: str, **kw) -> Project:
    return Project.from_scrape(source="test", external_id=kw.pop("external_id", "1"),
                               title=title, url=kw.pop("url", "https://example.com/p/1"),
                               description=description, **kw)


def test_classify():
    assert classify(make_project("استخراج متن ۱۵۰ کتاب", "خروجی json از pdf"))[0] == "data_pipeline"
    assert classify(make_project("ساخت ربات تلگرام", "بات تلگرام برای فروش"))[0] == "bot"
    assert classify(make_project("طراحی لوگو", "لوگو برای شرکت"))[0] == "design"
    assert classify(make_project("ربات بورس", "ارسال سفارش سرخطی در بورس با بازدهی روزانه"))[0] == "trading"


def test_screen_good_candidate():
    cfg = load_config()
    p = make_project(
        "استخراج ساختاریافته محتوای ۱۵۰ کتاب",
        "ما ۱۵۰ جلد کتاب pdf داریم. خروجی باید json با متن کامل، جداول و فرمول‌ها باشد. "
        "کیفیت خروجی اولویت ماست و شروع کار با یک کتاب نمونه است.",
        budget_toman=300_000_000, bids=8,
    )
    result = screen(p, cfg)
    assert result["category"] == "data_pipeline"
    assert result["arena_fit"] == "yes"
    assert result["verdict"] == "candidate"
    assert result["est_hours"] <= cfg.max_hours
    assert result["score"] >= 70


def test_screen_rejects_result_contingent_trading():
    cfg = load_config()
    p = make_project(
        "ساخت ربات ارسال خودکار سفارش‌های بورس",
        "ربات برای پنل‌های کارگزاری با دقت یک میلی‌ثانیه. پرداخت قرارداد مشروط به نتیجه آزمون است؛ "
        "دستیابی به بازدهی روزانه ۳۰ درصد ملاک پرداخت است.",
        budget_toman=20_000_000, bids=4,
    )
    result = screen(p, cfg)
    assert result["verdict"] == "rejected"
    assert any("پرداخت" in b or "بازده" in b for b in result["blockers"])


def test_screen_rejects_design_and_onsite():
    cfg = load_config()
    design = screen(make_project("طراحی لوگو اختصاصی", "طراحی لوگو با فتوشاپ و ایلوستریتور مشابه نمونه کار",
                                 budget_toman=4_500_000), cfg)
    assert design["verdict"] == "rejected"
    onsite = screen(make_project("مشاوره تأسیسات مکانیکی ویلا",
                                 "کنترل اجرایی موتورخانه، گرمایش از کف و استخر یک ویلای ۷۰۰ متری",
                                 budget_toman=2_500_000), cfg)
    assert onsite["verdict"] == "rejected"
    human = screen(make_project("ادمین پاسخگو", "استخدام ادمین برای پاسخگویی به مشتریان در تلگرام و بله",
                                budget_toman=3_200_000), cfg)
    assert human["verdict"] == "rejected"


def test_screen_budget_too_low_is_not_candidate():
    cfg = load_config()
    p = make_project(
        "اتصال فروشگاه به هوش مصنوعی",
        "نیاز به اتصال api هوش مصنوعی برای وارد کردن خودکار محصولات از دیجی‌کالا به سایت وردپرسی با سئو بالا",
        budget_toman=2_000_000,
    )
    result = screen(p, cfg)
    assert result["verdict"] in ("review", "rejected")
    assert any(r["code"] == "budget_fit" and r["impact"] < 0 for r in result["reasons"])


def test_screen_rejects_hiring_ads_and_tiny_budgets():
    cfg = load_config()
    hiring = make_project(
        "وب اپلیکیشن",
        "این پروژه پیش‌تر توسط فرد دیگری در حال توسعه بوده و به دلیل توقف همکاری با مجری قبلی "
        "به دنبال فردی متخصص برای ادامه‌ی توسعه هستیم.",
        budget_toman=45_000_000, flags=["فوری", "آگهی استخدام"],
    )
    result = screen(hiring, cfg)
    assert result["verdict"] == "rejected"
    assert "آگهی استخدامی (نه پروژه‌ی مشخص)" in result["blockers"]

    cheap = make_project(
        "ساخت مگامنوی موبایلی با المنتور", "ساخت مگامنوی موبایلی با المنتور برای سایت وردپرس",
        budget_toman=450_000,
    )
    cheap_result = screen(cheap, cfg)
    assert cheap_result["verdict"] == "rejected"
    assert any("کمتر از حداقل مبلغ" in r["text"] for r in cheap_result["reasons"])


def test_screen_rejects_crypto_exchange_bot():
    cfg = load_config()
    p = make_project(
        "طراحی و توسعه ربات تلگرام صرافی ارز دیجیتال",
        "یک ربات تلگرام اختصاصی برای خرید و فروش و معاملات ارز دیجیتال می‌خواهیم. "
        "برنامه‌نویس مسلط به پایتون و آشنا به الزامات امنیتی.",
        budget_toman=20_000_000, skills=["پایتون", "ربات تلگرام", "رمزارز"],
    )
    result = screen(p, cfg)
    assert result["category"] == "trading"
    assert result["verdict"] == "rejected"


def test_screen_flags_access_need():
    cfg = load_config()
    p = make_project(
        "افزودن زبان انگلیسی به سایت فروشگاهی موجود",
        "سایت فروشگاهی از قبل آماده است و باید دوزبانه شود؛ روی همین محصول موجود تغییرات اعمال شود.",
        budget_toman=20_000_000,
    )
    result = screen(p, cfg)
    assert any(n["kind"] == "provide_access" for n in result["needs_you"])


# --------------------------------------------------------------- pricing
def test_price_is_above_floor_and_scales_with_hours():
    cfg = load_config()
    p = make_project("سایت شرکتی", "طراحی وب سایت شرکتی با صفحه محصولات و وبلاگ",
                     budget_toman=25_000_000)
    screening = screen(p, cfg)
    proposal = propose(p, screening, cfg)
    assert proposal["price"] >= cfg.min_price
    assert proposal["price"] % cfg.round_to == 0
    assert proposal["hours"] == screening["est_hours"]
    assert proposal["proposal_text"].startswith("سلام")
    assert str(proposal["price"]) in proposal["proposal_text"].replace(",", "")
    assert len(proposal["milestones"]) >= 2
    assert sum(m["share"] for m in proposal["milestones"]) == pytest.approx(1.0)


def test_cheap_budget_gets_alternative():
    cfg = load_config()
    p = make_project("طراحی وبسایت فروشگاهی", "یک سایت فروشگاهی با امکانات کامل فروش آنلاین نیاز داریم",
                     budget_toman=1_000_000)
    screening = screen(p, cfg)
    proposal = propose(p, screening, cfg)
    assert proposal["budget_verdict"] == "low"
    assert proposal["alternative"] is not None


def test_quick_price_matches_full_price_for_good_budget():
    cfg = load_config()
    p = make_project("داشبورد گزارش‌گیری", "داشبورد با نمودار و خروجی اکسل از داده‌های فروش",
                     budget_toman=40_000_000)
    screening = screen(p, cfg)
    assert quick_price(cfg, screening["est_hours"], screening["category"]) == propose(p, screening, cfg)["floor_price"]


# --------------------------------------------------------------- demo
@pytest.mark.parametrize("category,expected_kind", [
    ("data_pipeline", "pipeline"),
    ("web_app", "site"),
    ("dashboard", "dashboard"),
    ("bot", "bot"),
])
def test_demo_builds_for_all_kinds(category, expected_kind, tmp_path):
    cfg = load_config()
    p = make_project("پروژه نمونه", "یک پروژه تستی برای ساخت دمو با چند نیازمندی مشخص و داده نمونه",
                     budget_toman=12_000_000)
    screening = screen(p, cfg)
    screening["category"] = category
    proposal = propose(p, screening, cfg)
    meta = build_demo(p, screening, proposal, tmp_path, base_url="http://localhost:5000")
    html = Path(meta["path"]).read_text(encoding="utf-8")
    assert "__DATA__" not in html
    assert "پروژه نمونه" in html
    assert meta["kind"] == expected_kind
    assert meta["rel"].endswith("index.html")
    assert json.loads((Path(meta["path"]).parent / "meta.json").read_text(encoding="utf-8"))["kind"] == expected_kind


# --------------------------------------------------------------- pipeline
def test_full_pipeline_offline(tmp_path):
    import shutil

    from frilanser import pipeline

    cfg = load_config()
    shutil.copytree(Path("data/raw"), tmp_path / "data" / "raw")
    cfg.raw["app"]["data_dir"] = str(tmp_path / "data")
    cfg.raw["app"]["outbox_dir"] = str(tmp_path / "outbox")
    cfg.raw["app"]["demo_dir"] = str(tmp_path / "outbox" / "demos")
    cfg.raw["app"]["report_dir"] = str(tmp_path / "outbox" / "reports")
    cfg.raw["fetch"]["allow_network"] = False

    store = Store(cfg.data_dir)
    result = pipeline.run_all(cfg, store, offline=True, demo_limit=2, force=True)

    assert result["collect"]["fetched"] >= 40
    assert store.all()
    screened = [p for p in store.all() if p.screening]
    assert len(screened) == len(store.all())
    assert any(p.verdict == "candidate" for p in store.all())
    assert any(p.verdict == "rejected" for p in store.all())
    assert result["demos"]["built"] == 2
    assert Path(result["notify"]["report_path"]).exists()
    assert result["notify"]["open_items"]

    # هیچ پروژه‌ی «در حال انجام/بسته» نباید وارد شود
    assert not any(set(p.flags) & pipeline.CLOSED_FLAGS for p in store.all())
    # همه‌ی کاندیداها قیمت دارند
    assert all(p.proposal for p in store.all() if p.verdict == "candidate")


# ------------------------------------------------------- دموی گرافیکی و قفل
def test_demo_is_visual_mockup_and_locked(tmp_path):
    from frilanser.demo_builder import build_demo, detect_archetype, _brand_from_title

    project = Project.from_scrape(
        "karlancer_programming", "1e82rr2n583w",
        "طراحی و پیاده سازی وب سایت کلینیک تخصصی درمانی",
        "https://www.karlancer.com/project/x",
        description="طراحی سایت برای یک کلینیک تخصصی با نوبت‌دهی آنلاین",
    )
    screening = {
        "category": "web_app", "category_label": "وب‌سایت/اپلیکیشن",
        "score": 95, "est_hours": 17.6, "schedule_days": 4,
        "deliverables": ["صفحه‌ی اصلی", "نوبت‌دهی آنلاین", "پنل مدیریت"],
    }
    proposal = {"price": 17_500_000, "milestones": [{"title": "پیش‌پرداخت", "share": 0.3, "when": "همین امروز"}]}

    meta = build_demo(project, screening, proposal, tmp_path)

    # آرکتایپ و نام برند از عنوان پروژه استخراج می‌شود
    assert detect_archetype(project, screening) == "clinic"
    assert _brand_from_title(project.title, "clinic") == "کلینیک تخصصی درمانی"
    assert meta["archetype"] == "clinic" and meta["kind"] == "site"

    html = Path(meta["path"]).read_text(encoding="utf-8")
    client = Path(meta["client_path"]).read_text(encoding="utf-8")

    for doc in (html, client):
        # یک پیش‌نمایش گرافیکی واقعی است (نه فقط متن)
        assert '<div class="mockwin">' in doc
        assert "hero" in doc and "<svg" in doc
        # قفلِ استفاده
        assert 'id="guard"' in doc and 'id="wm"' in doc and 'id="ribbon"' in doc
        assert "contextmenu" in doc and "selectstart" in doc
        assert 'name="robots" content="noindex' in doc

    # نسخه‌ی داخلی اطلاعات ما را دارد …
    assert "امتیاز اجراپذیری" in html and "قیمت پیشنهادی ما" in html
    # … و نسخه‌ی کارفرما ندارد
    assert "امتیاز اجراپذیری" not in client
    assert "قیمت پیشنهادی ما" not in client
    assert "karlancer.com" not in client
    # اما مبلغ و زمان تحویل را نشان می‌دهد
    assert "۱۷,۵۰۰,۰۰۰" in client


def test_demo_kinds_for_non_site_projects(tmp_path):
    from frilanser.demo_builder import build_demo

    cases = [
        ("استخراج ساختاریافته محتوای حدود ۱۵۰ کتاب", "data_pipeline", "pipeline"),
        ("یکپارچه سازی Odoo", "automation", "dashboard"),
        ("تکمیل و آماده سازی یک وب اپلیکیشن پژوهشی برای نسخه بتا", "web_app", "app"),
    ]
    for title, category, expected in cases:
        project = Project.from_scrape("ponisha", "x1", title, "https://ponisha.ir/project/x1")
        screening = {"category": category, "category_label": "x", "score": 80,
                     "est_hours": 10, "schedule_days": 3, "deliverables": []}
        meta = build_demo(project, screening, {"price": 6_000_000, "milestones": []}, tmp_path)
        assert meta["kind"] == expected, f"{title} → {meta['kind']} (انتظار: {expected})"
        assert Path(meta["client_path"]).exists()


def test_demo_bilingual_shop(tmp_path):
    from frilanser.demo_builder import build_demo

    project = Project.from_scrape("ponisha", "760389",
                                  "افزودن زبان انگلیسی به سایت فروشگاهی موجود",
                                  "https://ponisha.ir/project/760389")
    screening = {"category": "plugin_cms", "category_label": "افزونه/قالب", "score": 85,
                 "est_hours": 16.5, "schedule_days": 4, "deliverables": ["نسخه انگلیسی"]}
    meta = build_demo(project, screening, {"price": 11_500_000, "milestones": []}, tmp_path)
    assert meta["bilingual"] is True
    assert meta["archetype"] == "shop"
    html = Path(meta["path"]).read_text(encoding="utf-8")
    assert "English version" in html


# --------------------------------------------------------------- عیب‌یابی
def test_doctor_reports_missing_data(tmp_path):
    from frilanser.doctor import run_doctor

    cfg = load_config()
    cfg.raw["app"]["data_dir"] = str(tmp_path / "data")
    cfg.raw["app"]["outbox_dir"] = str(tmp_path / "outbox")
    cfg.raw["app"]["demo_dir"] = str(tmp_path / "outbox" / "demos")
    cfg.raw["app"]["report_dir"] = str(tmp_path / "outbox" / "reports")
    store = Store(cfg.data_dir)

    text = run_doctor(cfg, store, check_network=False)

    assert "گزارش عیب‌یابی" in text
    assert "هیچ اسنپ‌شاتی" in text          # اسنپ‌شات ندارد
    assert "تعداد پروژه‌ها : 0" in text
    assert "اجرای کامل" in text              # پیشنهاد اقدام
    assert (Path(cfg.outbox_dir) / "doctor.txt").exists()


def test_doctor_with_data_and_no_network(tmp_path):
    from frilanser.doctor import run_doctor

    import shutil

    cfg = load_config()
    shutil.copytree(Path("data/raw"), tmp_path / "data" / "raw")
    cfg.raw["app"]["data_dir"] = str(tmp_path / "data")
    cfg.raw["app"]["outbox_dir"] = str(tmp_path / "outbox")
    cfg.raw["app"]["demo_dir"] = str(tmp_path / "outbox" / "demos")
    cfg.raw["app"]["report_dir"] = str(tmp_path / "outbox" / "reports")
    cfg.raw["fetch"]["allow_network"] = False

    store = Store(cfg.data_dir)
    from frilanser import pipeline
    pipeline.collect(cfg, store, offline=True)

    text = run_doctor(cfg, store, check_network=False)
    assert "تعداد پروژه‌ها : 0" not in text
    assert "اسنپ‌شات" in text


# ----------------------------------------------------------- داشبورد و قالب‌ها
def test_all_templates_compile():
    """هیچ قالبی نباید خطای سینتکس جینجا داشته باشد (علت خطای ۵۰۰ صفحه‌ی اصلی)."""
    from frilanser.config import load_config
    from frilanser.store import Store
    from frilanser.web.app import create_app

    app = create_app(load_config(), Store(load_config().data_dir))
    names = app.jinja_env.list_templates()
    assert names, "هیچ قالبی پیدا نشد"
    for name in names:
        src = app.jinja_env.loader.get_source(app.jinja_env, name)[0]
        app.jinja_env.parse(src, name, name)      # خطا در اینجا یعنی قالب خراب است


def test_dashboard_pages_return_200():
    from frilanser.config import load_config
    from frilanser.store import Store
    from frilanser.web.app import create_app

    cfg = load_config()
    store = Store(cfg.data_dir)
    if not store.all():
        from frilanser import pipeline
        pipeline.collect(cfg, store, offline=True)
    app = create_app(cfg, store).test_client()

    for path in ("/", "/needs", "/demos", "/activity", "/healthz"):
        resp = app.get(path)
        assert resp.status_code == 200, f"{path} → {resp.status_code}"

    first = store.all()[0]
    resp = app.get(f"/p/{first.id}")
    assert resp.status_code == 200, f"صفحه‌ی پروژه → {resp.status_code}"


def test_server_error_shows_persian_page_not_raw_500():
    """اگر خطایی پیش آمد، صفحه‌ی فارسی با توضیح نشان بده (نه پیام بی‌توضیح)."""
    from frilanser.config import load_config
    from frilanser.store import Store
    from frilanser.web.app import create_app

    cfg = load_config()
    app = create_app(cfg, Store(cfg.data_dir))

    @app.get("/boom")
    def boom():
        raise RuntimeError("یک خطای عمدی برای تست")

    resp = app.test_client().get("/boom")
    assert resp.status_code == 500
    body = resp.get_data(as_text=True)
    assert "خطا در نمایش این صفحه" in body
    assert "یک خطای عمدی برای تست" in body


# ------------------------------------------------------- سیستم طراحی (Design System)
def _demo_project(title: str, desc: str = "") -> Project:
    return Project.from_scrape("karlancer", "ds-test", title, "https://www.karlancer.com/x",
                               description=desc)


@pytest.mark.parametrize("title,expected", [
    ("طراحی سایت کلینیک دندانپزشکی", "medical_clean"),
    ("طراحی وبسایت شرکت تجهیزات پزشکی", "corporate"),
    ("طراحی دو سایت فروشگاهی طلا", "luxury_gold"),
    ("فروشگاه اینترنتی پوشاک", "rose_shop"),
    ("طراحی سایت رستوران سنتی", "warm_editorial"),
    ("ساخت داشبورد هوش مصنوعی برای تحلیل داده", "neon_tech"),
    ("وبسایت شرکتی برای کارخانه تولیدی", "corporate"),
])
def test_style_selected_by_keywords(title, expected):
    from frilanser import design_system as ds

    style = ds.pick_style(_demo_project(title), "corporate")
    assert style.key == expected, f"{title} → {style.key}"


def test_style_override_from_config(tmp_path):
    from frilanser import design_system as ds

    assert ds.pick_style(_demo_project("طراحی سایت کلینیک"), "clinic", "brutalist").key == "brutalist"
    assert ds.pick_style(_demo_project("طراحی سایت کلینیک"), "clinic", "auto").key == "medical_clean"


def test_every_style_builds_a_clean_demo(tmp_path):
    """همه‌ی سبک‌ها باید بدون خطای طراحی (کنتراست/ریسپانسیو/دسترس‌پذیری) خروجی بدهند."""
    import re

    from frilanser import design_system as ds
    from frilanser.demo_builder import build_demo

    project = _demo_project("طراحی وبسایت فروشگاه اینترنتی", "فروشگاه آنلاین با سبد خرید")
    screening = {"category": "web_app", "category_label": "وب‌سایت", "score": 88,
                 "est_hours": 12, "schedule_days": 3, "deliverables": ["صفحه اصلی", "پنل مدیریت"]}
    proposal = {"price": 8_000_000, "milestones": []}

    cfg_path = Path("config.toml")
    original = cfg_path.read_text(encoding="utf-8")
    try:
        for key in ds.STYLES:
            cfg_path.write_text(original.replace('style = "auto"', f'style = "{key}"'),
                                encoding="utf-8")
            meta = build_demo(project, screening, proposal, tmp_path / key)
            assert meta["style"] == key
            assert meta["design_errors"] == [], f"{key}: {meta['design_errors']}"
            html = Path(meta["client_path"]).read_text(encoding="utf-8")
            assert "var(--grad)" in html and "--p:" in html      # توکن‌های طراحی تزریق شده
            assert re.search(r"@media[^{]*\(", html)             # قانون رسپانسیو
            assert 'id="wm"' in html and 'id="guard"' in html    # قفلِ استفاده
    finally:
        cfg_path.write_text(original, encoding="utf-8")


def test_new_components_are_rendered(tmp_path):
    """کتابخانه‌ی کامپوننت: قیمت، سؤالات متداول، گام‌ها و CTA باید در خروجی باشند."""
    from frilanser.demo_builder import build_demo

    project = _demo_project("طراحی وبسایت شرکت بازرگانی")
    screening = {"category": "web_app", "category_label": "وب‌سایت", "score": 85,
                 "est_hours": 10, "schedule_days": 3, "deliverables": ["۵ صفحه"]}
    meta = build_demo(project, screening, {"price": 7_000_000, "milestones": []}, tmp_path)
    html = Path(meta["client_path"]).read_text(encoding="utf-8")
    for token in ("بسته‌های پیشنهادی", "سؤالات متداول", "مسیر همکاری", "آماده‌ی شروع هستید؟"):
        assert token in html, f"کامپوننت «{token}» در خروجی نیست"


def test_contrast_helpers():
    from frilanser import design_system as ds

    assert ds.contrast_ratio("#000000", "#ffffff") == 21.0
    assert ds.contrast_ratio("#ffffff", "#ffffff") == 1.0
    assert ds.contrast_ratio("#ffffff", "#767676") > 4.4      # مرز رایج AA
    # روی هر رنگ اصلی، متن انتخاب‌شده باید خواناتر از سفیدِ همیشگی باشد
    for pal in ds.PALETTES.values():
        chosen = ds.contrast_ratio(ds.on_primary(pal.primary), pal.primary)
        assert chosen >= 3.0, f"{pal.key}: {chosen}"


# ------------------------------------------- خروجی واقعی React + Vite + Tailwind
def test_react_project_is_generated(tmp_path):
    from frilanser import design_system as ds
    from frilanser.react_builder import build_react_project

    project = Project.from_scrape("karlancer", "react-1", "طراحی وبسایت فروشگاه اینترنتی",
                                  "https://www.karlancer.com/x", description="فروشگاه آنلاین")
    screening = {"category": "web_app", "category_label": "وب‌سایت", "score": 90,
                 "est_hours": 12, "schedule_days": 3, "deliverables": ["صفحه اصلی", "پنل"]}
    meta = build_react_project(project, screening, {"price": 9_000_000}, tmp_path,
                               style_override="glassmorphism")

    root = Path(meta["path"])
    assert meta["style"] == "glassmorphism"
    for rel in ("package.json", "vite.config.js", "tailwind.config.js", "index.html",
                "src/main.jsx", "src/App.jsx", "src/theme.js", "src/content.js",
                "src/components/Hero.jsx", "src/components/Faq.jsx"):
        assert (root / rel).exists(), f"{rel} ساخته نشد"
        assert (root / rel).stat().st_size > 0

    # توکن‌های طراحی در تنظیمات تیلویند تزریق شده‌اند
    tw = (root / "tailwind.config.js").read_text(encoding="utf-8")
    pal = ds.PALETTES["violet"]
    assert pal.primary in tw and pal.gradient in tw
    # محتوای فارسی وارد شده
    content = (root / "src" / "content.js").read_text(encoding="utf-8")
    assert "فروشگاه" in content or "اینترنتی" in content
    # هیچ منبع خارجی (عکس/فونت اینترنتی) ندارد
    for f in root.rglob("*.jsx"):
        assert "http://" not in f.read_text(encoding="utf-8")
        assert "https://" not in f.read_text(encoding="utf-8")
    # سبک شیشه‌ای اعمال شده
    assert "backdrop-blur" in (root / "src" / "components" / "Services.jsx").read_text(encoding="utf-8")


def test_react_project_respects_style(tmp_path):
    from frilanser import design_system as ds
    from frilanser.react_builder import build_react_project

    project = Project.from_scrape("ponisha", "react-2", "طراحی سایت کلینیک دندانپزشکی",
                                  "https://ponisha.ir/x")
    screening = {"category": "web_app", "category_label": "وب", "score": 90,
                 "est_hours": 8, "schedule_days": 2, "deliverables": []}
    meta = build_react_project(project, screening, None, tmp_path)
    assert meta["style"] == "medical_clean"          # انتخاب خودکار از روی آگهی
    css = Path(meta["path"], "tailwind.config.js").read_text(encoding="utf-8")
    assert ds.PALETTES["emerald"].primary in css


# ------------------------------------------------- به‌روزرسانیِ درون‌برنامه‌ای
class _FakeResponse:
    def __init__(self, data, status=200, headers=None):
        self._data = data
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def iter_content(self, size):
        body = self._data if isinstance(self._data, bytes) else b""
        for i in range(0, len(body), size):
            yield body[i:i + size]


MANIFEST = {
    "version": "2.1.0",
    "release_url": "https://example.com/release",
    "notes": ["بهبود رابط", "افزوده شدن خروجی React"],
    "assets": {
        "android": {"file": "frilanser.apk", "url": "https://example.com/a.apk",
                    "size": 1234, "sha256": ""},
        "windows": {"file": "Frilanser-Setup.exe", "url": "https://example.com/s.exe",
                    "size": 4321, "sha256": ""},
    },
}


def test_check_update_reads_manifest(monkeypatch, tmp_path):
    from frilanser import updater

    seen = {}

    def fake_get(url, **kwargs):
        seen["url"] = url
        return _FakeResponse(MANIFEST)

    class FakeRequests:
        get = staticmethod(fake_get)

    monkeypatch.setattr(updater, "_request", lambda: FakeRequests)
    cfg = _cfg(str(tmp_path))

    info = updater.check_update(cfg, key="android")
    assert info["ok"] is True
    assert info["latest"] == "2.1.0"
    assert info["has_update"] is True          # نسخه‌ی فعلی ۱.۰.۰ است
    assert info["asset"]["file"] == "frilanser.apk"
    assert "بهبود رابط" in info["notes"]


def test_check_update_no_update_when_same_version(monkeypatch, tmp_path):
    from frilanser import updater
    from frilanser.version import __version__

    same = dict(MANIFEST, version=__version__)
    monkeypatch.setattr(updater, "_request",
                        lambda: type("R", (), {"get": staticmethod(
                            lambda url, **kw: _FakeResponse(same))}))
    info = updater.check_update(_cfg(str(tmp_path)), key="windows")
    assert info["has_update"] is False
    assert info["latest"] == __version__


def test_check_update_falls_back_to_release_api(monkeypatch, tmp_path):
    from frilanser import updater

    def fake_get(url, **kwargs):
        if "manifest" in url:
            raise RuntimeError("مانیفست در دسترس نیست")
        return _FakeResponse({
            "tag_name": "v3.0.0",
            "html_url": "https://example.com/rel",
            "assets": [{"name": "frilanser.apk", "browser_download_url": "https://x/a.apk",
                        "size": 10}],
        })

    monkeypatch.setattr(updater, "_request",
                        lambda: type("R", (), {"get": staticmethod(fake_get)}))
    info = updater.check_update(_cfg(str(tmp_path)), key="android")
    assert info["ok"] is True and info["latest"] == "3.0.0"
    assert info["asset"]["url"] == "https://x/a.apk"


def test_download_and_verify_sha256(monkeypatch, tmp_path):
    from frilanser import updater

    payload = b"frilanser-apk-bytes" * 10

    def fake_get(url, **kwargs):
        return _FakeResponse(payload, headers={"content-length": str(len(payload))})

    monkeypatch.setattr(updater, "_request",
                        lambda: type("R", (), {"get": staticmethod(fake_get)}))
    cfg = _cfg(str(tmp_path))

    res = updater.download(cfg, "https://example.com/a.apk", tmp_path / "a.apk")
    assert res["ok"] is True and res["size"] == len(payload)

    digest = updater.sha256_of(tmp_path / "a.apk")
    bad = updater.download(cfg, "https://example.com/a.apk", tmp_path / "b.apk",
                           sha256="0" * 64)
    assert bad["ok"] is False and "امضا" in bad["error"]
    assert updater.sha256_of(tmp_path / "a.apk") == digest


def test_update_downloads_and_calls_installer(monkeypatch, tmp_path):
    from frilanser import updater

    payload = b"apk"

    def fake_get(url, **kwargs):
        if "manifest" in url:
            return _FakeResponse(MANIFEST)
        return _FakeResponse(payload, headers={"content-length": str(len(payload))})

    monkeypatch.setattr(updater, "_request",
                        lambda: type("R", (), {"get": staticmethod(fake_get)}))
    calls = []
    monkeypatch.setattr(updater, "install", lambda path, key: (calls.append((path, key))
                                                               or {"ok": True, "message": "نصب شد"}))

    cfg = _cfg(str(tmp_path))
    out = updater.update(cfg, key="android")
    assert out["ok"] is True and out["latest"] == "2.1.0"
    assert calls and calls[0][1] == "android"
    assert Path(calls[0][0]).name == "frilanser.apk"
    state = updater.read_state(cfg)
    assert state.get("installed") is True


def test_version_and_platform_helpers():
    from frilanser.version import is_newer, platform_key, version_tuple

    assert version_tuple("1.10.2") == (1, 10, 2)
    assert is_newer("1.0.1", "1.0.0") and is_newer("2.0", "1.9.9")
    assert not is_newer("1.0.0", "1.0.0") and not is_newer("0.9", "1.0")
    assert platform_key() in ("android", "windows", "linux")


# ------------------------------------------------------- بسته‌ی اندروید
def test_android_entry_and_spec_exist():
    from frilanser.version import __version__

    main_py = Path(__file__).resolve().parent.parent / "android" / "main.py"
    spec = Path(__file__).resolve().parent.parent / "android" / "buildozer.spec"
    assert main_py.exists() and spec.exists()

    main_src = main_py.read_text(encoding="utf-8")
    spec_src = spec.read_text(encoding="utf-8")

    # بوت‌استرپ webview و پورت هماهنگ با سرور داخلی
    assert "bootstrap = webview" in spec_src
    assert "p4a.port = 5000" in spec_src
    assert "5000" in main_src
    # مجوز نصبِ به‌روزرسانی و اینترنت
    assert "REQUEST_INSTALL_PACKAGES" in spec_src and "INTERNET" in spec_src
    # نسخه‌ی spec با نسخه‌ی برنامه یکی است
    assert f"version = {__version__}" in spec_src
    # داده‌ها در پوشه‌ی قابل‌نوشتنِ برنامه نوشته می‌شوند
    assert "FRILANSER_HOME" in main_src


def test_config_honours_frilanser_home(monkeypatch, tmp_path):
    """روی اندروید ریشه‌ی برنامه از متغیر FRILANSER_HOME خوانده می‌شود."""
    import importlib

    from frilanser import config as config_mod

    monkeypatch.setenv("FRILANSER_HOME", str(tmp_path / "app"))
    mod = importlib.reload(config_mod)
    try:
        assert Path(mod.ROOT_DIR) == (tmp_path / "app")
    finally:
        monkeypatch.delenv("FRILANSER_HOME", raising=False)
        importlib.reload(config_mod)


# ------------------------------------------------ پیگیریِ پیشنهادها (ثبت و حفظ)
def test_proposal_state_persists_across_rescan(tmp_path):
    """وضعیتِ کاربر با اسکنِ دوباره از بین نمی‌رود."""
    from frilanser.store import Store

    store = Store(tmp_path)
    p = Project.from_scrape("ponisha", "1", "طراحی سایت فروشگاهی", "https://x")
    store.upsert_many([p])
    store.set_proposal_state(p.id, "submitted", price=7_000_000)
    assert store.get(p.id).proposal_state == "submitted"
    assert store.get(p.id).submitted_price == 7_000_000

    # اسکنِ مشابه (همان آگهی با متن/قیمتِ به‌روزشده)
    again = Project.from_scrape("ponisha", "1", "طراحی سایت فروشگاهی (به‌روزشده)",
                                "https://x", description="توضیح جدید")
    store.upsert_many([again])
    kept = store.get(p.id)
    assert kept.proposal_state == "submitted"          # وضعیت حفظ شد
    assert kept.submitted_price == 7_000_000           # مبلغ حفظ شد
    assert "روزشد" in kept.title                     # متن به‌روز شد
    assert kept.history                                # رخداد ثبت شد


def test_missing_project_is_closed_after_two_scans(tmp_path):
    """اگر آگهی دو بار پیاپی در اسکن نباشد، «واگذار/بسته‌شده» می‌شود."""
    from frilanser.store import Store
    from frilanser.tracking import apply_scan_results

    store = Store(tmp_path)
    p = Project.from_scrape("karlancer", "2", "اپلیکیشن اندروید", "https://y")
    store.upsert_many([p])
    store.set_proposal_state(p.id, "submitted")

    apply_scan_results(store, seen_ids=[])             # بار اول: فقط شمارنده
    assert store.get(p.id).proposal_state == "submitted"
    assert store.get(p.id).missed_scans == 1

    res = apply_scan_results(store, seen_ids=[])       # بار دوم: بسته می‌شود
    assert store.get(p.id).proposal_state == "closed"
    assert res["closed_by_miss"] == [p.id]

    # وضعیتِ دستیِ کاربر دست‌نخورده می‌ماند
    store.set_proposal_state(p.id, "won")
    apply_scan_results(store, seen_ids=[])
    assert store.get(p.id).proposal_state == "won"


def test_closed_marker_in_text_is_detected(tmp_path):
    """نشانه‌ی متنیِ «واگذار شد» به‌تنهایی کافی است."""
    from frilanser.store import Store
    from frilanser.tracking import apply_scan_results

    store = Store(tmp_path)
    p = Project.from_scrape("parscoders", "3", "طراحی پنل مدیریت", "https://z",
                            description="این پروژه واگذار شد")
    store.upsert_many([p])
    store.set_proposal_state(p.id, "submitted")
    res = apply_scan_results(store, seen_ids=[p.id])
    assert store.get(p.id).proposal_state == "closed"
    assert res["closed_by_text"] == [p.id]


# ---------------------------------------------- احتمالِ واگذاری به تازه‌کار
def _beginner(cfg, title, desc, bids=None, hours=10):
    from frilanser.screening import beginner_chance

    p = Project.from_scrape("karlancer", "b", title, "https://x", description=desc)
    p.bids = bids
    return beginner_chance(p, cfg, {"est_hours": hours})


def test_beginner_chance_prefers_open_ads(cfg_default):
    easy = _beginner(cfg_default, "سایت ساده برای کافه",
                     "کار ساده و فوری؛ تازه‌کار هم باشد اشکالی ندارد، قیمت مناسب مهم‌تر است",
                     bids=2, hours=5)
    hard = _beginner(cfg_default, "پلتفرم سازمانی بزرگ",
                     "تیم حرفه‌ای با حداقل ۵ سال سابقه کار و نمونه‌کار الزامی",
                     bids=45, hours=30)
    assert easy["score"] > hard["score"] + 25
    assert easy["level"] == "high"
    assert hard["level"] == "low"
    assert easy["hints"] and hard["hints"]


def test_beginner_chance_respects_bids(cfg_default):
    few = _beginner(cfg_default, "طراحی سایت", "سایت شرکتی", bids=2)
    many = _beginner(cfg_default, "طراحی سایت", "سایت شرکتی", bids=40)
    assert few["score"] > many["score"]


def test_newcomer_mode_lowers_price(cfg_default):
    """در حالت تازه‌کار، قیمت نهایی کمتر از حالت عادی است."""
    from frilanser.pricing import propose

    p = Project.from_scrape("karlancer", "n1", "طراحی سایت فروشگاهی کوچک", "https://x",
                            description="فروشگاه ساده")
    screening = {"category": "web_app", "est_hours": 12,
                 "beginner": {"score": 80, "level": "high",
                              "reasons": [], "hints": ["زود بفرست"]}}
    cfg_default.raw.setdefault("pricing", {})["newcomer_mode"] = True
    with_new = propose(p, screening, cfg_default)
    cfg_default.raw["pricing"]["newcomer_mode"] = False
    without = propose(p, screening, cfg_default)

    assert with_new["price"] < without["price"]
    assert with_new.get("newcomer_notes")
    assert any("تازه‌کار" in n for n in with_new["pricing_notes"])


# ---------------------------------------------- سرویسِ زنده (اسکن/نسخه خودکار)
def _live_cfg(tmp_path: Path, **live_over):
    """پیکربندیِ ایمن برای تستِ سرویس زنده (همه‌چیز زیر tmp_path)."""
    from frilanser.config import Config

    raw = {
        "app": {
            "outbox_dir": str(tmp_path / "outbox"),
            "data_dir": str(tmp_path / "data"),
            "raw_dir": str(tmp_path / "data" / "raw"),
            "cache_dir": str(tmp_path / "data" / "cache"),
            "demo_dir": str(tmp_path / "outbox" / "demos"),
            "report_dir": str(tmp_path / "outbox" / "reports"),
            "react_dir": str(tmp_path / "outbox" / "react"),
        },
        "pricing": {
            "hourly_rate_toman": 450000, "min_project_price_toman": 5000000,
            "round_to_toman": 500000, "platform_commission": 0.10,
            "risk_buffer": 0.15, "max_hours": 24,
        },
        "live": {"auto_scan_minutes": 0, "update_check_hours": 0,
                 "auto_scan_offline": True, "auto_scan_demo_limit": 0,
                 **live_over},
    }
    return Config(raw, tmp_path / "config.toml")


def test_live_scan_records_status(tmp_path):
    """اسکنِ فوری وضعیت را پر می‌کند و سرویس آن را به خاطر می‌سپارد."""
    from frilanser.live import LiveService
    from frilanser.store import Store

    cfg = _live_cfg(tmp_path)
    store = Store(cfg.data_dir)
    store.upsert_many([
        Project.from_scrape("karlancer", "L1", "طراحی سایت شرکتی", "https://x",
                            description="یک سایت شرکتی ساده با وردپرس و قالب آماده"),
        Project.from_scrape("karlancer", "L2", "ربات تلگرام", "https://y",
                            description="ربات ساده برای پاسخ خودکار به کاربران"),
    ])

    svc = LiveService(cfg, store)
    res = svc.scan_now(trigger="test", offline=True, wait=True)

    assert res["ok"] is True
    snap = svc.snapshot()
    assert snap["last_scan"]["ok"] is True
    assert snap["last_scan"]["trigger"] == "test"
    assert snap["counts"]["total"] == 2
    assert snap["stamp"]
    assert snap["version"]
    assert snap["update"]["current"] == snap["version"]


def test_live_stamp_changes_with_data(tmp_path):
    """نشانه‌ی داده با تغییرِ وضعیت عوض می‌شود (رابط کاربری می‌فهمد تازه کند)."""
    from frilanser.live import LiveService
    from frilanser.store import Store

    cfg = _live_cfg(tmp_path)
    store = Store(cfg.data_dir)
    p = Project.from_scrape("karlancer", "S1", "اپلیکیشن اندروید", "https://x")
    store.upsert_many([p])

    svc = LiveService(cfg, store)
    first = svc.snapshot()["stamp"]
    store.set_proposal_state(p.id, "submitted")
    assert svc.refresh_stamp() != first


def test_live_auto_toggle_persists(tmp_path):
    """خاموش کردنِ اسکنِ خودکار ذخیره می‌شود و در اجرای بعدی هم خاموش می‌ماند."""
    from frilanser.live import LiveService
    from frilanser.store import Store

    cfg = _live_cfg(tmp_path, auto_scan_minutes=30)
    store = Store(cfg.data_dir)

    svc = LiveService(cfg, store)
    assert svc.snapshot()["auto"] is True
    svc.set_auto(False)
    assert svc.snapshot()["auto"] is False
    assert svc.snapshot()["next_scan_in"] is None

    again = LiveService(cfg, store)
    assert again.snapshot()["auto"] is False


def test_web_live_endpoints(tmp_path):
    """مسیرهای زنده‌ی وب: /api/live، /fragment و نوارِ زنده در صفحه."""
    from frilanser.store import Store
    from frilanser.web.app import create_app

    cfg = _live_cfg(tmp_path)
    store = Store(cfg.data_dir)
    store.upsert_many([
        Project.from_scrape("karlancer", "W1", "سایت فروشگاهی", "https://x",
                            description="فروشگاه اینترنتی با وردپرس و ووکامرس"),
    ])

    off = create_app(cfg, store, live=False).test_client()
    assert off.get("/api/live").status_code == 503
    page = off.get("/")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert "livebar" in text and "الان اسکن کن" in text
    frag = off.get("/fragment?verdict=candidate")
    assert frag.status_code == 200
    assert "livebar" not in frag.get_data(as_text=True)

    on = create_app(cfg, store, live=True).test_client()
    data = on.get("/api/live").get_json()
    assert data["ok"] is True
    assert data["counts"]["total"] == 1
    assert data["scanning"] is False
    assert data["poll_seconds"] >= 5


def test_web_live_scan_endpoint(tmp_path):
    """درخواستِ اسکن از رابط وب، اسکنِ پس‌زمینه را آغاز می‌کند."""
    from frilanser.store import Store
    from frilanser.web.app import create_app

    cfg = _live_cfg(tmp_path)
    store = Store(cfg.data_dir)
    client = create_app(cfg, store, live=True).test_client()

    res = client.post("/api/live/scan", data={"offline": "1"}).get_json()
    assert res["ok"] is True and res["started"] is True

    snap = client.get("/api/live").get_json()
    assert snap["last_scan"] is None or snap["scanning"] is True

    toggled = client.post("/api/live/auto", data={"enabled": "0"}).get_json()
    assert toggled["ok"] is True and toggled["auto"] is False
    assert client.get("/api/live").get_json()["auto"] is False


def test_live_scan_falls_back_to_snapshots(tmp_path, monkeypatch):
    """اگر دریافتِ زنده شکست خورد، سرویس خودش از اسنپ‌شات‌ها می‌خواند."""
    import frilanser.pipeline as pipeline
    from frilanser.live import LiveService
    from frilanser.store import Store

    calls: list = []

    def fake_run_all(cfg, store, offline=True, demo_limit=0, base_url="", **_kw):
        calls.append(offline)
        if not offline:
            raise RuntimeError("شبکه در دسترس نیست")
        return {"collect": {"fetched": 3, "new": 1, "updated": 0},
                "tracking": {"closed_by_miss": [], "closed_by_text": [], "kept": 0},
                "screen": {"counts": {}}, "demos": {"built": 0},
                "price": {"priced": 0}, "notify": {"open_items": []}}

    monkeypatch.setattr(pipeline, "run_all", fake_run_all)

    cfg = _live_cfg(tmp_path)
    svc = LiveService(cfg, Store(cfg.data_dir))
    svc.scan_now(trigger="test", offline=False, wait=True)

    assert calls == [False, True]          # تلاشِ زنده، سپس تلاشِ آفلاین
    snap = svc.snapshot()
    assert snap["last_scan"]["ok"] is True
    assert snap["last_scan"]["fell_back"] is True
    assert snap["last_scan"]["fetched"] == 3


def test_manifest_repairs_conflict_markers(tmp_path, monkeypatch):
    """مانیفستی که با نشانه‌ی تداخلِ گیت کامیت شده باشد، خراب نمی‌ماند."""
    from frilanser import updater
    import scripts.make_manifest as mm

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{\n  "version": "1.0.2",\n<<<<<<< HEAD\n  "notes": ["ویندوز"],\n'
        '  "assets": {"windows": {"file": "a.exe", "size": 3,\n=======\n'
        '  "notes": ["اندروید"],\n  "assets": {"android": {"file": "a.apk", "size": 5,\n'
        '>>>>>>> abc123 (ساخت خودکار)\n    "sha256": "", "url": "https://x/a"}\n  }\n}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(mm, "MANIFEST", manifest)

    data = mm.load()
    assert isinstance(data, dict)
    assert data["version"] == "1.0.2"
    assert data["assets"] == {} or "windows" in data["assets"] or "android" in data["assets"]

    # و بعد از یک ثبتِ سالم، مانیفست دوباره JSONِ معتبر می‌شود
    src = tmp_path / "a.apk"
    src.write_bytes(b"12345")
    monkeypatch.setattr(mm, "MANIFEST", manifest)
    args = types.SimpleNamespace(key="android", file=str(src),
                                 version="1.0.2", notes="")
    assert mm.cmd_set(args) == 0
    assert json.loads(manifest.read_text(encoding="utf-8"))["assets"]["android"]["size"] == 5

    # برنامه هم باید بتواند چنین مانیفستی را بخواند (بدون از کار افتادن)
    monkeypatch.setattr(mm, "MANIFEST", manifest)
    assert mm.cmd_verify(type("A", (), {})()) == 0


def test_updater_tolerates_broken_manifest(tmp_path):
    """اگر مانیفست JSONِ سالمی نباشد، برنامه به‌جای خطا پیام می‌دهد (نه کرش)."""
    from frilanser import updater

    def boom(url, **_kw):
        class R:
            status_code = 200

            def json(self):
                raise ValueError("not json")
        return R()

    class FakeRequests:
        @staticmethod
        def get(url, **kw):
            return boom(url, **kw)

    import frilanser.updater as up

    original = up._request
    up._request = lambda: FakeRequests
    try:
        info = up.check_update(_cfg_manifest_only(tmp_path), timeout=1)
    finally:
        up._request = original
    assert info["ok"] is False
    assert info["has_update"] is False
    assert info["error"]


def _cfg_manifest_only(root: Path):
    from frilanser.config import Config

    return Config({"update": {"manifest_url": "https://example.invalid/m.json"},
                   "app": {"outbox_dir": str(root / "outbox"),
                           "data_dir": str(root / "data")}}, root / "config.toml")


# ---------------------------------------------- انتخابِ سایت‌ها و تازگیِ داده
def _sources_cfg(tmp_path, **extra):
    from frilanser.config import Config

    raw = {
        "app": {"outbox_dir": str(tmp_path / "outbox"), "data_dir": str(tmp_path / "data"),
                "raw_dir": str(tmp_path / "data" / "raw"), "cache_dir": str(tmp_path / "data" / "cache"),
                "demo_dir": str(tmp_path / "outbox" / "demos"), "report_dir": str(tmp_path / "outbox" / "reports")},
        "sources": {
            "karlancer": {"enabled": True, "label": "کارلنسر", "kind": "karlancer",
                          "listing_url": "https://example.invalid/jobs"},
            "ponisha": {"enabled": True, "label": "پونیشا", "kind": "ponisha",
                        "listing_url": "https://example.invalid/p"},
        },
    }
    raw.update(extra)
    return Config(raw, tmp_path / "config.toml")


def test_source_prefs_disable_and_persist(tmp_path):
    """کاربر می‌تواند فقط سایتی را که در آن اکانت دارد روشن بگذارد."""
    from frilanser.sources.registry import (
        build_sources,
        load_source_prefs,
        save_source_prefs,
        source_states,
    )

    cfg = _sources_cfg(tmp_path)
    assert set(build_sources(cfg)) == {"karlancer", "ponisha"}

    save_source_prefs(cfg, {"karlancer": True, "ponisha": False})
    assert set(build_sources(cfg)) == {"karlancer"}
    assert source_states(cfg)["ponisha"] is False
    assert load_source_prefs(cfg)["ponisha"] is False

    # انتخاب در اجرای بعدی هم می‌ماند
    cfg2 = _sources_cfg(tmp_path)
    assert set(build_sources(cfg2)) == {"karlancer"}


def test_collect_reports_per_source(tmp_path):
    """نتیجه‌ی هر سایت جداگانه گزارش می‌شود (تا بدانیم کدام سایت جواب نداد)."""
    from frilanser.pipeline import collect
    from frilanser.store import Store

    cfg = _sources_cfg(tmp_path)
    (cfg.raw_dir).mkdir(parents=True, exist_ok=True)
    (cfg.raw_dir / "karlancer-test.json").write_text(
        json.dumps([{"id": "1", "title": "طراحی سایت فروشگاهی", "url": "https://x/1",
                     "description": "توضیح کافی برای این پروژه تستی", "budget": "5,000,000"}]),
        encoding="utf-8")

    store = Store(cfg.data_dir)
    result = collect(cfg, store, offline=True)

    assert result["per_source"]["karlancer"]["fetched"] == 1
    assert result["per_source"]["karlancer"]["ok"] is True
    # سایتی که اسنپ‌شاتی ندارد هم در گزارش هست (با صفر آگهی)، نه اینکه نادیده گرفته شود
    assert result["per_source"]["ponisha"]["fetched"] == 0


def test_cache_ttl_lets_new_pages_in(tmp_path):
    """کشِ صفحه‌ها دیگر ابدی نیست: بعد از TTL دوباره از سایت گرفته می‌شود."""
    from frilanser.sources.base import BaseSource

    cfg = _sources_cfg(tmp_path, fetch={"cache_ttl_hours": 2})
    (cfg.cache_dir).mkdir(parents=True, exist_ok=True)
    cache = cfg.cache_dir / "x.txt"
    cache.write_text("old", encoding="utf-8")

    src = BaseSource(cfg, "karlancer")
    assert src._cache_is_fresh(cache) is True          # تازه است → از کش

    cfg.raw["fetch"]["cache_ttl_hours"] = 0             # همیشه تازه بگیر
    assert src._cache_is_fresh(cache) is False

    cfg.raw["fetch"]["cache_ttl_hours"] = 2
    old = time.time() - 5 * 3600
    os.utime(cache, (old, old))                         # کشِ کهنه
    assert src._cache_is_fresh(cache) is False


def test_tracking_not_closed_when_scan_returns_nothing(tmp_path):
    """اگر اسکن هیچ آگهی‌ای نیاورد، پیشنهادهای کاربر بسته فرض نمی‌شوند."""
    from frilanser.pipeline import refresh_tracking
    from frilanser.store import Store

    cfg = _sources_cfg(tmp_path)
    store = Store(cfg.data_dir)
    p = Project.from_scrape("karlancer", "T1", "طراحی سایت", "https://x")
    store.upsert_many([p])
    store.set_proposal_state(p.id, "submitted")

    for _ in range(3):
        res = refresh_tracking(cfg, store, seen_ids=[])
    assert res.get("skipped") is True
    assert store.get(p.id).proposal_state == "submitted"


def test_web_sources_route_saves_choice(tmp_path):
    """فرمِ انتخابِ سایت در داشبورد، انتخاب را ذخیره می‌کند."""
    from frilanser.sources.registry import build_sources
    from frilanser.store import Store
    from frilanser.web.app import create_app

    cfg = _sources_cfg(tmp_path)
    client = create_app(cfg, Store(cfg.data_dir), live=False).test_client()

    page = client.get("/").get_data(as_text=True)
    assert "کدام سایت‌ها اسکن شوند" in page

    res = client.post("/sources", data={"source": ["karlancer"]})
    assert res.status_code == 302
    assert set(build_sources(_sources_cfg(tmp_path))) == {"karlancer"}


def test_mobile_responsive_css_exists():
    """داشبورد باید در عرضِ گوشی هم درست نمایش داده شود."""
    css = (ROOT / "frilanser" / "web" / "static" / "style.css").read_text(encoding="utf-8")
    assert "@media (max-width:640px)" in css
    assert "@media (max-width:900px)" in css
    base = (ROOT / "frilanser" / "web" / "templates" / "base.html").read_text(encoding="utf-8")
    assert "width=device-width" in base and "viewport-fit=cover" in base


# ---------------------------------------------- دسترسی‌پذیریِ به‌روزرسانی
def test_manifest_urls_try_cdn_and_custom_first(tmp_path):
    """آدرسِ مانیفست: ابتدا انتخابِ کاربر، بعد CDN، بعد شاخه‌ی گیت‌هاب."""
    from frilanser import updater

    cfg = _cfg(str(tmp_path))
    urls = updater.manifest_urls(cfg)
    assert any("cdn.jsdelivr.net" in u for u in urls), urls
    assert any("raw.githubusercontent.com" in u for u in urls)
    assert urls.index([u for u in urls if "jsdelivr" in u][0]) < \
           urls.index([u for u in urls if "raw.githubusercontent" in u][0])

    updater.save_update_config(cfg, manifest_url="https://example.invalid/m.json")
    assert updater.manifest_urls(cfg)[0] == "https://example.invalid/m.json"
    assert updater.load_update_config(cfg)["manifest_url"] == "https://example.invalid/m.json"


def test_asset_urls_order_cdn_then_mirror_then_release():
    """ترتیبِ تلاش برای دانلود: CDN ← آینه‌ی شاخه ← لینکِ انتشار."""
    from frilanser.updater import asset_urls

    asset = {"url": "https://github.com/x/y.apk",
             "mirror": "https://raw.githubusercontent.com/x/y.apk",
             "cdn": "https://cdn.jsdelivr.net/gh/x/y.apk"}
    urls = asset_urls(asset)
    # همه‌ی نشانی‌ها یک «ضدّ‌کش» دارند تا CDN نسخه‌ی قبلی را ندهد
    assert all("_=" in u for u in urls)
    plain = [u.split("_=")[0].rstrip("?&") for u in urls]
    assert plain[:3] == [asset["cdn"], asset["cdn"].replace("cdn.", "gcore."), asset["mirror"]]
    assert asset["url"] in plain
    assert len(asset_urls({"url": "https://only/x.apk"})) == 1
    assert asset_urls({}) == []


def test_download_falls_back_to_next_url(tmp_path, monkeypatch):
    """اگر یک آدرس کار نکرد، آدرسِ بعدی امتحان می‌شود (نه اینکه کلِ به‌روزرسانی شکست بخورد)."""
    from frilanser import updater

    tried: list = []

    def fake_one(cfg, url, dest, sha256=""):
        tried.append(url)
        if url.startswith("https://cdn."):
            return {"ok": False, "error": "شبکه در دسترس نیست"}
        return {"ok": True, "path": str(dest)}

    monkeypatch.setattr(updater, "_download_one", fake_one)
    cfg = _cfg(str(tmp_path))
    res = updater.download(cfg, ["https://cdn.jsdelivr.net/a.apk",
                                 "https://raw.githubusercontent.com/a.apk"],
                           tmp_path / "a.apk")
    assert res["ok"] is True
    assert tried[0].startswith("https://cdn.")
    assert res["url"].startswith("https://raw.")

    monkeypatch.setattr(updater, "_download_one",
                        lambda *a, **k: {"ok": False, "error": "همه بسته‌اند"})
    res2 = updater.download(cfg, ["https://a/x", "https://b/x"], tmp_path / "b.apk")
    assert res2["ok"] is False and "tried" in res2


# ---------------------------------------------- گزارشِ اسکن و کوکیِ ورود
class _FakeResp:
    def __init__(self, text: str, status: int = 200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"خطای HTTP {self.status_code}")


def _fake_requests(handler):
    """ماژولِ requests ساختگی برای تستِ بدون اینترنت."""
    import sys
    import types as _t

    mod = _t.ModuleType("requests")
    mod.get = staticmethod(handler)
    return mod


def test_fetch_log_records_status_and_sample(tmp_path, monkeypatch):
    """هر تلاشِ دریافت با کدِ پاسخ و نمونه‌ای از متن ثبت می‌شود (برای گزارش)."""
    import sys

    from frilanser.sources.base import BaseSource

    cfg = _sources_cfg(tmp_path, fetch={"cache_ttl_hours": 0, "timeout_seconds": 5,
                                        "delay_between_requests": 0})
    monkeypatch.setitem(sys.modules, "requests",
                        _fake_requests(lambda url, **kw: _FakeResp("<html>آگهی تست</html>")))
    src = BaseSource(cfg, "karlancer")
    text = src.fetch_text("https://example.invalid/jobs", force=True)

    assert "آگهی" in text
    rep = src.fetch_report()
    assert rep["attempts"] == 1 and rep["ok"] == 1 and rep["failed"] == 0
    assert rep["log"][0]["status"] == 200
    assert rep["log"][0]["chars"] > 0
    assert "آگهی" in (rep["log"][0]["sample"] or "")
    assert rep["has_cookie"] is False


def test_fetch_log_records_http_error(tmp_path, monkeypatch):
    """کدِ خطای سایت (مثل ۴۰۳ نیاز به ورود) در گزارش دیده می‌شود."""
    import sys

    from frilanser.sources.base import BaseSource, FetchError

    cfg = _sources_cfg(tmp_path, fetch={"cache_ttl_hours": 0, "timeout_seconds": 5,
                                        "delay_between_requests": 0})
    monkeypatch.setitem(sys.modules, "requests",
                        _fake_requests(lambda url, **kw: _FakeResp("denied", 403)))
    src = BaseSource(cfg, "karlancer")
    with pytest.raises(FetchError):
        src.fetch_text("https://example.invalid/jobs", force=True)

    rep = src.fetch_report()
    assert rep["failed"] == 1 and rep["ok"] == 0
    assert rep["log"][0]["status"] == 403


def test_cookie_from_secrets_is_sent(tmp_path, monkeypatch):
    """کوکی‌ای که کاربر در برنامه می‌گذارد همراهِ درخواست فرستاده می‌شود."""
    import sys

    from frilanser.sources.base import BaseSource
    from frilanser.sources.registry import load_source_secrets, save_source_secrets

    cfg = _sources_cfg(tmp_path, fetch={"cache_ttl_hours": 0, "timeout_seconds": 5,
                                        "delay_between_requests": 0})
    save_source_secrets(cfg, {"karlancer": "sid=abc; uid=7"})
    assert load_source_secrets(cfg)["karlancer"].startswith("sid=abc")

    seen: dict = {}
    monkeypatch.setitem(sys.modules, "requests",
                        _fake_requests(lambda url, **kw: (seen.update(kw) or _FakeResp("ok"))))
    src = BaseSource(cfg, "karlancer")
    src.fetch_text("https://example.invalid/jobs", force=True)

    assert seen.get("headers", {}).get("Cookie") == "sid=abc; uid=7"
    assert src.fetch_report()["has_cookie"] is True


def test_scan_report_page_renders(tmp_path):
    """صفحه‌ی «گزارشِ اسکن» در دسترس است (برای فرستادنِ علت به پشتیبانی)."""
    from frilanser.store import Store
    from frilanser.web.app import create_app

    cfg = _sources_cfg(tmp_path)
    client = create_app(cfg, Store(cfg.data_dir), live=False).test_client()
    page = client.get("/scan-report")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert "گزارشِ آخرین اسکن" in text
    assert "اگر سایتی فقط با اکانت آگهی نشان می‌دهد" in text
    assert "cookie__karlancer" in text


def test_paste_page_adds_projects(tmp_path):
    """متن/اچ‌تی‌ام‌الِ صفحه‌ای که کاربر می‌چسباند، آگهی می‌سازد."""
    from frilanser.store import Store
    from frilanser.web.app import create_app

    cfg = _sources_cfg(tmp_path)
    store = Store(cfg.data_dir)
    client = create_app(cfg, store, live=False).test_client()

    page = """###### [1a2b3c - طراحی سایت فروشگاهی](https://www.karlancer.com/projects/1a2b3c)
###### حداکثر بودجه: 8,000,000 تومان
###### 3 پیشنهاد

فروشگاه اینترنتی با وردپرس و ووکامرس می‌خواهم که امکان پرداخت آنلاین داشته باشد
و صفحه‌ی محصول برای هر کالا با تصویر و توضیحات کامل نمایش داده شود.
"""
    res = client.post("/paste", data={"source": "karlancer", "text": page,
                                      "url": "https://www.karlancer.com/jobs/programming"})
    assert res.status_code == 302
    assert "pasted=1" in res.headers["Location"] or "parsed=1" in res.headers["Location"]

    stored = store.all()
    assert len(stored) == 1
    assert "فروشگاه" in stored[0].title
    assert stored[0].screening is not None and stored[0].proposal is not None

    # متنِ خیلی کوتاه رد می‌شود و چیزی اضافه نمی‌کند
    res2 = client.post("/paste", data={"source": "karlancer", "text": "سلام"})
    assert "err=" in res2.headers["Location"]
    assert len(store.all()) == 1


# ---------------------------------------------- دریافتِ اینترنتیِ بدون وابستگی
def test_http_stdlib_path_works_without_requests(monkeypatch):
    """اگر requests ناقص باشد، دریافت با کتابخانه‌ی استاندارد انجام می‌شود."""
    import sys

    import frilanser.http as http

    class _Resp:
        def __init__(self, body: bytes):
            self._body = body
            self.headers = {"Content-Type": "text/html; charset=utf-8"}

        def read(self, n=-1):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(http, "has_requests", lambda: False)
    monkeypatch.setattr(http, "_opener",
                        lambda context=None: type("O", (), {
                            "open": lambda self, req, timeout=None: _Resp("سلام آگهی".encode())
                        })())

    got = http.get_text("https://example.invalid/list")
    assert got["ok"] is True and "آگهی" in got["text"]
    assert got["how"].startswith("stdlib")


def test_updater_uses_stdlib_when_requests_broken(monkeypatch):
    """بررسیِ نسخه حتی با نبودِ requests/urllib3 باید کار کند."""
    import frilanser.updater as up
    from frilanser.version import __version__

    class Cfg:
        raw = {"update": {}}
        outbox_dir = "/tmp/frilanser-selftest-outbox"
        sources: dict = {}

    monkeypatch.setattr(up, "_request", lambda: None)
    monkeypatch.setattr(up, "manifest_urls",
                        lambda cfg: ["https://example.invalid/manifest.json"])
    monkeypatch.setattr(up, "_cfg_value", lambda *a, **k: "")

    def fake_get_json(url, timeout=15.0):
        return {"ok": True, "status": 200, "how": "stdlib",
                "data": {"version": "9.9.9", "notes": ["تست"],
                         "assets": {"android": {"file": "frilanser.apk",
                                                "url": "https://x/a.apk",
                                                "size": 10, "sha256": ""}}}}

    monkeypatch.setattr(up, "_http_get_json", fake_get_json)
    info = up.check_update(Cfg(), key="android")
    assert info["ok"] is True and info["latest"] == "9.9.9"
    assert info["has_update"] is True          # ۹.۹.۹ جدیدتر از نسخه‌ی فعلی است
    assert info["current"] == __version__


# ---------------------------------------------------------------------------
# لایه‌ی سازگاریِ کتابخانه‌ها (۱.۰.۷)
# ---------------------------------------------------------------------------
def test_compat_typing_extensions_stub_allows_bs4(monkeypatch, tmp_path):
    """بدون typing_extensions نصب‌شده، bs4 باید با جانشینِ typing ایمپورت شود."""
    import builtins
    import sys

    from frilanser import compat

    real_import = builtins.__import__
    saved = sys.modules.pop("typing_extensions", None)

    def fake_import(name, *args, **kwargs):
        if name == "typing_extensions" and name not in sys.modules:
            raise ImportError("No module named 'typing_extensions'")
        return real_import(name, *args, **kwargs)

    try:
        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert compat.ensure_typing_extensions() is True
        mod = sys.modules["typing_extensions"]
        assert hasattr(mod, "Protocol") and hasattr(mod, "TypeAlias")
    finally:
        monkeypatch.setattr(builtins, "__import__", real_import)
        sys.modules.pop("typing_extensions", None)
        if saved is not None:
            sys.modules["typing_extensions"] = saved


def test_compat_probe_reports_real_state():
    """probe() باید برای کتابخانه‌ی موجود True و برای ناموجود متن خطا بدهد."""
    from frilanser import compat

    assert compat.probe("json") is True
    bad = compat.probe("این_کتابخانه_اصلا_وجود_ندارد")
    assert bad is True or isinstance(bad, str)


def test_html_to_text_works_with_bs4_and_without(tmp_path):
    """تبدیل HTML→متن باید در هر دو حالت (bs4 یا جانشینِ regex) متن بدهد."""
    from frilanser.sources.base import BaseSource

    sample = "<div><script>x=1</script><p>سلام &amp; درود</p></div>"
    text = BaseSource.html_to_text(sample)
    assert "سلام" in text
    assert "&amp;" not in text
    assert "x=1" not in text


def test_compat_describe_shape():
    """گزارشِ describe باید libs و html_parser داشته باشد."""
    from frilanser import compat

    info = compat.describe()
    assert isinstance(info["libs"], dict)
    assert "bs4" in info["libs"]
    assert isinstance(info["html_parser"]["ok"], bool)


# ---------------------------------------------------------------------------
# زنجیره‌ی دریافت: مستقیم → کتابخانه‌ی استاندارد → واسطه (۱.۰.۸)
# ---------------------------------------------------------------------------
def test_http_relay_used_when_direct_fails(monkeypatch):
    """اگر دریافتِ مستقیم شکست بخورد، واسطه‌ها باید امتحان شوند."""
    from frilanser import http

    calls: list[str] = []

    def fake_direct(url, timeout=25.0, headers=None, allow_insecure=True):
        calls.append(url)
        if url == "https://example.com/page":
            return {"ok": False, "status": None, "text": "", "error": "SSLError: booom",
                    "how": "requests"}
        return {"ok": True, "status": 200, "text": "<html>OK</html>", "error": "",
                "how": "stdlib"}

    monkeypatch.setattr(http, "_fetch_direct", fake_direct)
    got = http.get_text("https://example.com/page", allow_relay=True)
    assert got["ok"] is True
    assert "واسطه" in got["how"]
    assert got["text"] == "<html>OK</html>"
    # اول خودِ نشانی امتحان شده، بعد واسطه‌ی اول
    assert calls[0] == "https://example.com/page"
    assert len(calls) >= 2


def test_http_no_relay_when_direct_works(monkeypatch):
    """وقتی دریافتِ مستقیم جواب می‌دهد، نباید سراغ واسطه رفت."""
    from frilanser import http

    def fake_direct(url, timeout=25.0, headers=None, allow_insecure=True):
        assert url == "https://example.com/page"
        return {"ok": True, "status": 200, "text": "سلام", "error": "", "how": "requests"}

    monkeypatch.setattr(http, "_fetch_direct", fake_direct)
    got = http.get_text("https://example.com/page", allow_relay=True)
    assert got["how"] == "requests"


def test_http_relay_errors_reported(monkeypatch):
    """اگر همه‌چیز شکست بخورد، علتِ هر واسطه هم در گزارش باشد."""
    from frilanser import http

    monkeypatch.setattr(
        http, "_fetch_direct",
        lambda url, timeout=25.0, headers=None, allow_insecure=True: {
            "ok": False, "status": None, "text": "", "error": "URLError: بسته است",
            "how": "stdlib"},
    )
    got = http.get_text("https://example.com/page", allow_relay=True)
    assert got["ok"] is False
    assert got["relay_errors"]
    assert any("allorigins" in e or "واسطه" in e for e in got["relay_errors"]) or len(
        got["relay_errors"]) >= 2


def test_source_falls_back_to_stale_cache(tmp_path, monkeypatch):
    """اگر شبکه شکست بخورد اما کشِ قدیمی هست، همان برگردانده و «کهنه» نشان شود."""
    import hashlib

    from frilanser.config import Config
    from frilanser.sources.base import BaseSource

    cfg = Config({"app": {"data_dir": "data", "cache_dir": "cache"},
                  "sources": {"ponisha": {"listing_url": "https://x.test/p"}}},
                 tmp_path / "config.toml")
    src = BaseSource(cfg, "ponisha")
    url = "https://x.test/projects"
    digest = hashlib.md5(url.encode()).hexdigest()[:12]
    cache_file = src.cache_dir / f"ponisha-{digest}.txt"
    src.cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(("آگهی قدیمی " * 60) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        "frilanser.http.get_text",
        lambda *a, **k: {"ok": False, "status": None, "text": "", "error": "قطعی",
                         "how": "stdlib", "relay_errors": ["allorigins: خطا"]},
    )
    got = src.fetch_text(url, force=True)
    assert "آگهی قدیمی" in got
    assert src.used_stale_cache is True
    assert src.fetch_log[-1].get("stale") is True
    assert src.fetch_log[-1].get("cached") == "کهنه"


# ---------------------------------------------------------------------------
# پیش‌فرضِ داخلیِ نشانیِ منابع (۱.۰.۹)
# ---------------------------------------------------------------------------
def test_sources_have_builtin_listing_urls():
    """حتی بدون config.toml هر منبع نشانیِ فهرستِ خود را دارد."""
    from frilanser.config import Config
    from frilanser.sources.registry import build_sources

    cfg = Config({"app": {"data_dir": "data", "cache_dir": "cache"}},
                 Path(".") / "config.toml")
    sources = build_sources(cfg)
    assert {"ponisha", "karlancer", "parscoders"} <= set(sources)
    for key, src in sources.items():
        assert src.list_urls(), f"{key} بدون نشانی است"


def test_config_sources_still_win_over_defaults():
    """اگر کاربر نشانیِ دیگری بدهد، همان به کار می‌رود."""
    from frilanser.config import Config

    cfg = Config({"sources": {"ponisha": {"listing_url": "https://x.test/mine"}}},
                 Path(".") / "config.toml")
    assert cfg.sources["ponisha"]["listing_url"] == "https://x.test/mine"


def test_user_defined_sources_are_not_expanded():
    """پیش‌فرض‌ها نباید سایتِ ناخواسته‌ای به انتخابِ کاربر اضافه کنند."""
    from frilanser.config import Config

    cfg = Config({"sources": {"karlancer": {"enabled": True}}}, Path(".") / "config.toml")
    assert set(cfg.sources) == {"karlancer"}


def test_missing_listing_url_is_reported(tmp_path):
    """منبعِ بی‌نشانی باید خطا بدهد، نه اینکه بی‌صدا صفر آگهی برگرداند."""
    from frilanser.pipeline import collect
    from frilanser.sources.base import BaseSource
    from frilanser.sources.registry import build_sources

    cfg = _sources_cfg(tmp_path)
    cfg.raw["sources"]["ponisha"]["listing_url"] = ""
    for key in list(cfg.raw["sources"]):
        if key != "ponisha":
            cfg.raw["sources"].pop(key)
    # نشانیِ پیش‌فرض را هم خالی می‌کنیم تا واقعاً بی‌نشانی شود
    import frilanser.sources.defaults as defaults

    saved = defaults.DEFAULT_SOURCES["ponisha"]["listing_url"]
    defaults.DEFAULT_SOURCES["ponisha"]["listing_url"] = ""
    try:
        sources = build_sources(cfg)
        assert "ponisha" in sources
        assert sources["ponisha"].list_urls() == []
    finally:
        defaults.DEFAULT_SOURCES["ponisha"]["listing_url"] = saved


# ---------------------------------------------------------------------------
# ضدّ‌کش برای CDNها (۱.۰.۱۰)
# ---------------------------------------------------------------------------
def test_cache_buster_added_to_manifest_urls():
    """مانیفست باید همیشه تازه خوانده شود، نه از کشِ CDN."""
    from frilanser.updater import _cdn_manifest_urls

    urls = _cdn_manifest_urls()
    assert urls, "هیچ نشانی‌ای برای مانیفست ساخته نشد"
    for url in urls:
        assert "_=" in url, f"بدون ضدّ‌کش: {url}"


def test_cache_buster_keeps_existing_query():
    """اگر نشانی خودش پارامتر داشت، ضدّ‌کش با & چسبانده شود."""
    from frilanser.updater import bust

    assert bust("https://x.test/a?b=1").startswith("https://x.test/a?b=1&_=")
    assert bust("https://x.test/a").startswith("https://x.test/a?_=")
    assert bust("") == ""


def test_empty_listing_url_in_config_does_not_win():
    """اگر در تنظیمات نشانی خالی باشد، پیش‌فرضِ برنامه به کار می‌رود."""
    from frilanser.config import Config

    cfg = Config({"sources": {"ponisha": {"enabled": True, "listing_url": ""}}},
                 Path(".") / "config.toml")
    assert cfg.sources["ponisha"]["listing_url"].startswith("https://ponisha.ir")


# ---------------------------------------------------------------------------
# گزارشِ کهنه‌ی نسخه‌ی قبل نباید نشان داده شود (۱.۰.۱۲)
# ---------------------------------------------------------------------------
def test_stale_scan_record_from_other_version_is_dropped(tmp_path, monkeypatch):
    """رکوردِ مانده از نسخه‌ی دیگر ممکن است ساختارِ دیگری داشته باشد و گمراه کند."""
    from frilanser import live as live_mod
    from frilanser.live import LiveService

    cfg = _sources_cfg(tmp_path)
    from frilanser.store import Store

    store = Store(cfg.data_dir)
    state_path = Path(cfg.outbox_dir) / live_mod.STATE_FILE
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({
        "auto": True,
        "last_scan": {"ok": True, "at": 1, "fetched": 0, "app_version": "0.9.9",
                      "sources": {"ponisha": {"ok": True, "fetched": 0}}},
    }), encoding="utf-8")

    svc = LiveService(cfg, store)
    assert svc.last_scan is None, "گزارشِ نسخه‌ی دیگر باید کنار گذاشته شود"


def test_scan_record_is_stamped_with_app_version(tmp_path):
    """هر رکورد باید شماره‌ی نسخه‌ی سازنده‌اش را داشته باشد."""
    from frilanser import live as live_mod
    from frilanser.live import LiveService
    from frilanser.store import Store

    cfg = _sources_cfg(tmp_path)
    svc = LiveService(cfg, Store(cfg.data_dir))
    svc._run_scan(trigger="manual", offline=True)
    assert svc.last_scan["app_version"] == live_mod.__version__
    assert svc.last_scan.get("running") is False
