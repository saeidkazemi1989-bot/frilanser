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
    n = result["notify"]
    print()
    print("=" * 70)
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
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
