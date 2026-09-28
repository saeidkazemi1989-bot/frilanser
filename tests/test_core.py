"""تست‌های هسته‌ی فریلنس‌یار آرنا (بدون نیاز به اینترنت)."""

from __future__ import annotations

import json
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
