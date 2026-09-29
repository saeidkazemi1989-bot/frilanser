"""رابط خط فرمان: python -m frilanser <دستور>"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Config, load_config
from .models import VERDICT_LABELS, STATUS_LABELS
from .store import Store


def get_context(args) -> tuple[Config, Store]:
    cfg = load_config(getattr(args, "config", None))
    store = Store(cfg.data_dir)
    return cfg, store


def _print_table(projects, limit: int | None = None) -> None:
    rows = projects[:limit] if limit else projects
    print(f"{'امتیاز':>4}  {'بودجه':>14}  {'قیمت ما':>14}  {'ساعت':>5}  {'منبع':<20} عنوان")
    print("-" * 110)
    for p in rows:
        budget = f"{p.budget_toman:,}" if p.budget_toman else "—"
        price = f"{(p.proposal or {}).get('price', 0):,}" if p.proposal else "—"
        hours = (p.screening or {}).get("est_hours", "—")
        print(f"{p.score:>4}  {budget:>14}  {price:>14}  {str(hours):>5}  "
              f"{p.source_label[:20]:<20} {p.title[:45]}")


# ------------------------------------------------------------------ commands
def cmd_run(args):
    cfg, store = get_context(args)
    result = None
    from . import pipeline
    result = pipeline.run_all(
        cfg, store,
        offline=not args.online,
        refresh=args.refresh,
        demo_limit=args.demos,
        base_url=args.base_url,
        force=args.force,
        demo_verdicts=tuple(v.strip() for v in args.verdicts.split(",") if v.strip()),
    )
    if result["collect"]["fetched"] == 0:
        print()
        print("!" * 70)
        print("هیچ آگهی‌ای پیدا نشد. دلیل را در گزارش زیر ببینید:")
        print("!" * 70)
        from .doctor import run_doctor

        print(run_doctor(cfg, store, check_network=not args.online))
        return 1

    n = result["notify"]
    print()
    print("=" * 70)
    print(f"آگهی‌های بررسی‌شده: {result['collect']['fetched']} | "
          f"کاندیدا: {result['screen']['counts'].get('candidate', 0)} | "
          f"پیش‌نمایش ساخته‌شده: {result['demos']['built']}")
    print(f"گزارش: {n['report_path']}")
    print(f"کارهایی که باید خودتان انجام دهید: {len(n['open_items'])} مورد")
    for item in n["open_items"][:10]:
        print(f"  • [{item['kind_label']}] {item['project_title'][:60]}")
    return 0


def cmd_scan(args):
    cfg, store = get_context(args)
    from . import pipeline
    res = pipeline.collect(cfg, store, offline=not args.online, refresh=args.refresh)
    print(f"\nدریافت: {res['fetched']} | جدید: {res['new']} | به‌روزرسانی: {res['updated']}")
    return 0


def cmd_screen(args):
    cfg, store = get_context(args)
    from . import pipeline
    res = pipeline.screen_projects(cfg, store, force=args.force)
    print(f"غربال شد: {res['screened']} → {res['counts']}")
    return 0


def cmd_propose(args):
    cfg, store = get_context(args)
    from . import pipeline
    res = pipeline.price_projects(cfg, store, force=args.force)
    print(f"قیمت‌گذاری شد: {res['priced']} پروژه")
    return 0


def cmd_demo(args):
    cfg, store = get_context(args)
    from . import pipeline
    res = pipeline.build_demos(
        cfg, store,
        verdicts=tuple(v.strip() for v in args.verdicts.split(",") if v.strip()),
        limit=args.limit, base_url=args.base_url, force=args.force,
        style=getattr(args, "style", "") or "",
        only=getattr(args, "project", "") or "",
    )
    print(f"تعداد دموهای ساخته‌شده: {res['built']}")
    return 0


def cmd_report(args):
    cfg, store = get_context(args)
    from . import pipeline
    res = pipeline.notify(cfg, store)
    print(res["report_path"])
    return 0


def cmd_list(args):
    cfg, store = get_context(args)
    projects = store.all()
    if args.verdict:
        projects = [p for p in projects if p.verdict == args.verdict]
    if args.status:
        projects = [p for p in projects if p.status == args.status]
    print(f"تعداد: {len(projects)}\n")
    _print_table(projects, args.top)
    return 0


def cmd_show(args):
    cfg, store = get_context(args)
    p = store.get(args.id) or next((x for x in store.all() if args.id in x.id or args.id in x.url), None)
    if not p:
        print("پیدا نشد. از دستور list کمک بگیرید.")
        return 1
    s, pr = p.screening or {}, p.proposal or {}
    print("=" * 78)
    print(p.title)
    print("=" * 78)
    print(f"منبع      : {p.source_label}")
    print(f"لینک      : {p.url}")
    print(f"بودجه     : {p.budget_toman:,} تومان" if p.budget_toman else "بودجه     : اعلام نشده")
    print(f"مهلت/زمان : {p.client_deadline_days} روز" if p.client_deadline_days else "")
    print(f"تعداد پیشنهادها: {p.bids}")
    print(f"وضعیت     : {STATUS_LABELS.get(p.status, p.status)} | تصمیم شما: {p.user_decision or '—'}")
    if s:
        print("-" * 78)
        print(f"دسته      : {s['category_label']}")
        print(f"اجرا در آرنا: {s['fit_label']}  | امتیاز: {s['score']}/100 | رای: {VERDICT_LABELS.get(s['verdict'])}")
        print(f"زمان برآوردی: {s['est_hours']} ساعت ≈ {s['schedule_days']} روز کاری")
        print("دلایل:")
        for r in s["reasons"]:
            sign = "+" if r["impact"] > 0 else ("-" if r["impact"] < 0 else "•")
            print(f"   {sign} {r['text']}")
        if s["blockers"]:
            print("موانع: " + "، ".join(s["blockers"]))
    if pr:
        print("-" * 78)
        print(f"قیمت پیشنهادی: {pr['price']:,} تومان (کف: {pr['floor_price']:,})")
        print(f"نسبت به بودجه: {pr['budget_verdict']} (بودجه/قیمت = {pr['budget_ratio']})")
        for note in pr["pricing_notes"]:
            print("   · " + note)
        if p.demo:
            print(f"دمو       : {p.demo['url']}")
        print("-" * 78)
        print(pr["proposal_text"])
    return 0


def cmd_needs(args):
    cfg, store = get_context(args)
    items = [i for i in store.needs_you() if not i.get("done")] if args.open else store.needs_you()
    if not items:
        print("موردی وجود ندارد.")
        return 0
    for i, item in enumerate(items, 1):
        print(f"{i}. [{item['kind_label']}] {item['project_title']}")
        print(f"   چه کاری: {item['text']}")
        print(f"   چطور   : {item['how']}")
        if item.get("url"):
            print(f"   لینک   : {item['url']}")
        if args.full and item.get("proposal_text"):
            print("   --- متن پیشنهاد ---")
            for line in item["proposal_text"].splitlines():
                print("   " + line)
        print()
    return 0


def cmd_decide(args):
    cfg, store = get_context(args)
    from . import pipeline
    p = pipeline.set_decision(store, args.id, args.decision, note=args.note)
    if not p:
        print("پیدا نشد.")
        return 1
    print(f"{p.title[:60]} → {args.decision} ({STATUS_LABELS.get(p.status, p.status)})")
    return 0


def cmd_react(args):
    """ساخت پروژه‌ی واقعی React + Vite + Tailwind برای یک پروژه."""
    cfg, store = get_context(args)
    from .react_builder import build_react_project

    needle = args.project or ""
    targets = [p for p in store.all() if needle in p.id or needle in p.title] if needle \
        else [p for p in store.all() if p.verdict == "candidate"]

    if args.limit:
        targets = targets[: args.limit]
    if not targets:
        print("پروژه‌ای پیدا نشد؛ شناسه یا بخشی از عنوان را بدهید: --project کلینیک")
        return 1

    out_dir = Path(args.out) if args.out else Path(cfg.raw.get("app", {}).get("react_dir", "outbox/react"))
    out_dir.mkdir(parents=True, exist_ok=True)

    for project in targets:
        meta = build_react_project(project, project.screening or {}, project.proposal,
                                   out_dir, style_override=args.style or "")
        print(f"✓ پروژه‌ی React ساخته شد ({meta['files']} فایل): {project.title[:46]}")
        print(f"    مسیر: {meta['path']}")
        print(f"    سبک: {meta['style_label']} · برای اجرا: npm install && npm run dev")
    return 0


def cmd_track(args):
    """فهرستِ پیشنهادهای شما و وضعیت هر کدام (در به‌روزرسانی‌ها حفظ می‌شود)."""
    cfg, store = get_context(args)
    from .models import PROPOSAL_STATES

    mine = [p for p in store.all() if p.proposal_state]
    if not mine:
        print("هیچ پیشنهادی ثبت نشده است.")
        print("برای ثبت: frilanser state <شناسه> submitted --price 7000000")
        print("یا از داشبورد، صفحه‌ی هر پروژه، دکمه‌ی «پیشنهاد دادم» را بزنید.")
        return 0

    order = {"won": 0, "submitted": 1, "lost": 2, "closed": 3}
    mine.sort(key=lambda p: (order.get(p.proposal_state, 9), -(p.score or 0)))

    counts: dict[str, int] = {}
    for p in mine:
        counts[p.proposal_state] = counts.get(p.proposal_state, 0) + 1
    print("خلاصه: " + " | ".join(
        f"{PROPOSAL_STATES.get(k, k)}: {v}" for k, v in sorted(counts.items(),
                                                                key=lambda kv: order.get(kv[0], 9))))
    print()
    print(f"{'وضعیت':18} {'امتیاز':>6} {'تازه‌کار':>8} {'مبلغ شما':>12}  عنوان")
    print("-" * 96)
    for p in mine:
        beg = (p.screening or {}).get("beginner") or {}
        price = f"{p.submitted_price:,}" if p.submitted_price else "—"
        print(f"{PROPOSAL_STATES.get(p.proposal_state, ''):18} {p.score or 0:6} "
              f"{beg.get('score', 0):8} {price:>12}  {p.title[:44]}")
    print()
    print("نکته: اگر پروژه‌ای از فهرست سایت حذف شود، پس از دو اسکنِ پیاپی")
    print("خودکار «واگذار/بسته‌شده» علامت می‌خورد و در گزارش می‌آید.")
    return 0


def cmd_state(args):
    """ثبت یا پاک کردنِ وضعیتِ پیشنهاد برای یک پروژه."""
    cfg, store = get_context(args)
    from .models import PROPOSAL_STATES

    state = (args.state or "").strip().lower()
    aliases = {"submitted": "submitted", "submit": "submitted", "sent": "submitted",
               "won": "won", "win": "won",
               "lost": "lost", "lose": "lost", "rejected": "lost",
               "closed": "closed", "close": "closed", "done": "closed",
               "": "", "clear": "", "none": ""}
    if state not in aliases:
        print(f"وضعیت نامعلوم: {state}")
        print("گزینه‌ها: submitted | won | lost | closed | clear")
        return 1
    state = aliases[state]

    project = store.set_proposal_state(args.project_id, state, price=args.price)
    if project is None:
        print(f"پروژه‌ای با این شناسه پیدا نشد: {args.project_id}")
        print("شناسه‌ها را با: frilanser list  ببینید.")
        return 1
    from . import pipeline

    pipeline.notify(cfg, store)
    print(f"✓ {project.title[:56]}")
    print(f"  وضعیت: {PROPOSAL_STATES.get(state, 'بدون وضعیت')}")
    if project.submitted_price:
        print(f"  مبلغ پیشنهادی شما: {project.submitted_price:,} تومان")
    return 0


def cmd_update(args):
    """بررسی/دریافت/نصب نسخه‌ی جدید برنامه."""
    cfg, store = get_context(args)
    from . import updater
    from .version import __version__, platform_key

    print(f"نسخه‌ی فعلی: {__version__} ({platform_key()})")
    if args.check_only:
        info = updater.check_update(cfg)
        if not info["ok"]:
            print(f"بررسی ناموفق بود: {info['error']}")
            return 1
        print(f"آخرین نسخه: {info['latest']}")
        if info["has_update"]:
            print(f"نسخه‌ی جدید موجود است ({info['asset'].get('size', 0):,} بایت)")
            for note in info["notes"][:6]:
                print(f"  • {note}")
            if info.get("release_url"):
                print(f"توضیحات: {info['release_url']}")
        else:
            print("برنامه به‌روز است ✓")
        return 0

    res = updater.update(cfg, auto_install=not args.download_only)
    if not res.get("ok"):
        print(f"به‌روزرسانی ناموفق بود: {res.get('error') or res.get('message', '')}")
        return 1
    print(res.get("message") or "به‌روزرسانی انجام شد")
    if res.get("downloaded"):
        print(f"فایل: {res['downloaded']}")
    return 0


def cmd_styles(args):
    """فهرست سبک‌های طراحیِ قابل انتخاب برای پیش‌نمایش‌ها."""
    from . import design_system as ds

    print("سبک‌های طراحی موجود (در config.toml بخش [demo] مقدار style را تنظیم کنید):\n")
    for key, label, desc, pal in ds.list_styles():
        print(f"  {key:16} {label:22} — {desc}")
        print(f"  {'':16} پالت: {pal}")
    print("\nمثال: style = \"glassmorphism\"   (پیش‌فرض: auto یعنی انتخاب خودکار از روی آگهی)")
    return 0


def cmd_doctor(args):
    """گزارش عیب‌یابی: چرا داده نمی‌آید (و چه باید کرد)."""
    cfg, store = get_context(args)
    from .doctor import run_doctor

    text = run_doctor(cfg, store, check_network=not args.offline, timeout=args.timeout)
    print(text)
    print()
    print(f"این گزارش در فایل زیر هم ذخیره شد: {Path(cfg.outbox_dir) / 'doctor.txt'}")
    return 0


def cmd_paths(args):
    """نمایش مسیرهای مؤثر — برای عیب‌یابی (مخصوصاً در نسخه‌ی EXE)."""
    import sys

    cfg, store = get_context(args)
    from .config import BUNDLE, ROOT

    def info(p):
        p = Path(p)
        if not p.exists():
            return f"{p} (وجود ندارد)"
        if p.is_dir():
            try:
                return f"{p} ({len(list(p.iterdir()))} مورد)"
            except OSError as exc:  # pragma: no cover
                return f"{p} (خطا: {exc})"
        return f"{p} ({p.stat().st_size} بایت)"

    print(f"نسخه                 : {__import__('frilanser').__version__}")
    print(f"اجرای فریز‌شده (EXE) : {bool(getattr(sys, 'frozen', False))}")
    print(f"sys.executable       : {sys.executable}")
    print(f"sys._MEIPASS         : {getattr(sys, '_MEIPASS', '-')}")
    print(f"پوشه‌ی پروژه (ROOT)  : {info(ROOT)}")
    print(f"پوشه‌ی باندل (BUNDLE): {info(BUNDLE)}")
    print(f"فایل تنظیمات         : {info(cfg.path)}")
    print(f"پوشه‌ی داده‌ها       : {info(cfg.data_dir)}")
    print(f"پوشه‌ی اسنپ‌شات‌ها   : {info(cfg.raw_dir)}")
    print(f"پوشه‌ی خروجی         : {info(cfg.outbox_dir)}")
    print(f"پوشه‌ی پروژه‌های React: {info(cfg.react_dir)}")
    print(f"قالب‌های وب          : {info(Path(__file__).parent / 'web' / 'templates')}")
    bundle_raw = Path(BUNDLE) / "data" / "raw"
    print(f"اسنپ‌شات‌های باندل   : {info(bundle_raw)}")
    return 0


def cmd_serve(args):
    cfg, store = get_context(args)
    from .web.app import create_app
    app = create_app(cfg, store)
    url = f"http://127.0.0.1:{args.port}"
    print(f"داشبورد روی http://{args.host}:{args.port} در دسترس است ({url})")
    if args.open:
        import threading
        import webbrowser

        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    return 0


# ------------------------------------------------------------------ parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="frilanser",
        description="فریلنس‌یار آرنا — پیدا کردن و غربال کردن پروژه‌های فریلنسری ایرانی",
    )
    parser.add_argument("--config", help="مسیر فایل تنظیمات (پیش‌فرض config.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="اجرای کامل خط لوله")
    p.add_argument("--online", action="store_true", help="دریافت زنده از سایت‌ها (نیاز به اینترنت)")
    p.add_argument("--refresh", action="store_true", help="نادیده گرفتن کش")
    p.add_argument("--demos", type=int, default=3, help="حداکثر تعداد دمو")
    p.add_argument("--verdicts", default="candidate", help="برای چه رای‌هایی دمو ساخته شود")
    p.add_argument("--base-url", default="", help="آدرس پایه برای لینک دموها")
    p.add_argument("--force", action="store_true", help="محاسبه‌ی مجدد حتی اگر انجام شده")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("scan", help="جمع‌آوری آگهی‌ها")
    p.add_argument("--online", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("screen", help="غربالگری پروژه‌ها")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_screen)

    p = sub.add_parser("propose", help="قیمت‌گذاری")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_propose)

    p = sub.add_parser("demo", help="ساخت دمو")
    p.add_argument("--style", default="", help="سبک طراحی (مثل glassmorphism؛ خالی = خودکار)")
    p.add_argument("--project", default="", help="فقط این پروژه (شناسه یا بخشی از عنوان)")
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--verdicts", default="candidate,review")
    p.add_argument("--base-url", default="")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("report", help="ساخت گزارش و صف نیاز به ورود شما")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("list", help="فهرست پروژه‌ها")
    p.add_argument("--verdict", choices=list(VERDICT_LABELS))
    p.add_argument("--status", choices=list(STATUS_LABELS))
    p.add_argument("--top", type=int)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="نمایش جزئیات یک پروژه")
    p.add_argument("id")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("needs", help="کارهایی که باید خودتان انجام دهید")
    p.add_argument("--open", action="store_true", help="فقط موارد انجام‌نشده")
    p.add_argument("--full", action="store_true", help="نمایش متن کامل پیشنهاد")
    p.set_defaults(func=cmd_needs)

    p = sub.add_parser("decide", help="ثبت تصمیم شما")
    p.add_argument("id")
    p.add_argument("decision", choices=["approved", "rejected", "delivered"])
    p.add_argument("--note", default=None)
    p.set_defaults(func=cmd_decide)

    p = sub.add_parser("react", help="ساخت پروژه‌ی واقعی React + Vite + Tailwind")
    p.add_argument("--project", default="", help="شناسه یا بخشی از عنوان پروژه")
    p.add_argument("--style", default="", help="سبک طراحی (مثل glassmorphism)")
    p.add_argument("--out", default="", help="پوشه‌ی خروجی (پیش‌فرض outbox/react)")
    p.add_argument("--limit", type=int, default=0, help="حداکثر تعداد پروژه")
    p.set_defaults(func=cmd_react)

    p = sub.add_parser("track", help="فهرستِ پیشنهادهای شما و وضعیت هر کدام")
    p.set_defaults(func=cmd_track)

    p = sub.add_parser("state", help="ثبت وضعیتِ پیشنهاد (داده‌ام/گرفتم/نگرفتم/بسته شد)")
    p.add_argument("project_id", help="شناسه‌ی پروژه (مثل ponisha:760397)")
    p.add_argument("state", help="submitted | won | lost | closed | clear")
    p.add_argument("--price", type=int, default=None, help="مبلغی که پیشنهاد داده‌اید (تومان)")
    p.set_defaults(func=cmd_state)

    p = sub.add_parser("update", help="به‌روزرسانی برنامه به آخرین نسخه")
    p.add_argument("--check-only", action="store_true", help="فقط بررسی کن، چیزی نصب نکن")
    p.add_argument("--download-only", action="store_true", help="فقط دانلود کن، نصب نکن")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("styles", help="فهرست سبک‌های طراحی پیش‌نمایش‌ها")
    p.set_defaults(func=cmd_styles)

    p = sub.add_parser("doctor", help="عیب‌یابی: چرا داده نمی‌آید و چه باید کرد")
    p.add_argument("--offline", action="store_true", help="بررسی نکردنِ اینترنت")
    p.add_argument("--timeout", type=float, default=6.0)
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("paths", help="نمایش مسیرهای مورد استفاده (عیب‌یابی)")
    p.set_defaults(func=cmd_paths)

    p = sub.add_parser("serve", help="اجرای داشبورد وب")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--open", action="store_true", help="باز کردن خودکار مرورگر")
    p.add_argument("--debug", action="store_true")
    p.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # در نسخه‌ی اجرایی (EXE) فایل‌های پیش‌فرض را کنار برنامه می‌گذاریم تا قابل ویرایش باشند
    try:
        from .config import bootstrap_user_files, load_config

        copied = bootstrap_user_files(load_config(getattr(args, "config", None)))
        for item in copied:
            print(f"· فایل پیش‌فرض ایجاد شد: {item}")
    except Exception as exc:  # pragma: no cover - نباید مانع اجرا شود
        print(f"هشدار: آماده‌سازی پوشه‌ی کاربر انجام نشد ({exc})")

    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
