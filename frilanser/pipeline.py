"""هماهنگی مراحل خط لوله: جمع‌آوری ← غربالگری ← قیمت‌گذاری ← ساخت دمو ← اطلاع‌رسانی."""

from __future__ import annotations

from typing import Iterable

from .config import Config
from .demo_builder import build_demo
from .models import (
    STATUS_AWAITING,
    STATUS_BUILT,
    STATUS_DELIVERED,
    STATUS_REJECTED,
    STATUS_SCREENED,
    Project,
)
from .sources.registry import build_sources, collect_snapshots
from .store import Store


# ------------------------------------------------------------------ collect
CLOSED_FLAGS = {"درحال انجام", "بسته شده", "منقضی شده", "لغو شده", "تکمیل شده", "خاتمه یافته"}


def collect(cfg: Config, store: Store, offline: bool = True, refresh: bool = False,
            extra_urls: Iterable[str] | None = None) -> dict:
    sources = build_sources(cfg)
    projects: list[Project] = []
    if offline:
        projects = collect_snapshots(cfg, sources)
    else:
        for source in sources.values():
            projects.extend(source.collect(extra_urls=extra_urls, force=refresh))
        if not projects:  # اگر دسترسی نبود، از اسنپ‌شات استفاده کن
            print("  ! دریافت زنده ناموفق بود؛ از اسنپ‌شات‌های محلی استفاده می‌شود")
            projects = collect_snapshots(cfg, sources)

    # آگهی‌های بسته/در حال انجام را کنار می‌گذاریم
    before = len(projects)
    projects = [p for p in projects if not (set(p.flags) & CLOSED_FLAGS)]
    if before != len(projects):
        print(f"  · {before - len(projects)} آگهی بسته‌شده/در حال انجام حذف شد")

    new, updated = store.upsert_many(projects)
    store.log("collect", "-", f"{new} جدید / {updated} به‌روزرسانی (offline={offline})")
    return {"fetched": len(projects), "new": new, "updated": updated, "sources": list(sources)}


# ------------------------------------------------------------------ screen
def screen_projects(cfg: Config, store: Store, force: bool = False) -> dict:
    from .screening import screen

    counts = {"candidate": 0, "review": 0, "rejected": 0}
    changed = 0
    for project in store.all():
        if project.screening and not force:
            counts[project.verdict] = counts.get(project.verdict, 0) + 1
            continue
        project.screening = screen(project, cfg)
        if project.status in ("new", ""):
            project.status = STATUS_SCREENED
        counts[project.verdict] = counts.get(project.verdict, 0) + 1
        changed += 1
    store.save()
    store.log("screen", "-", f"{changed} پروژه غربال شد: {counts}")
    return {"screened": changed, "counts": counts}


# ------------------------------------------------------------------ price
def price_projects(cfg: Config, store: Store, force: bool = False) -> dict:
    from .pricing import propose

    priced = 0
    for project in store.all():
        if not project.screening:
            continue
        if project.proposal and not force:
            continue
        project.proposal = propose(project, project.screening, cfg,
                                   demo_url=(project.demo or {}).get("url"))
        priced += 1
    store.save()
    store.log("price", "-", f"{priced} قیمت‌گذاری")
    return {"priced": priced}


# ------------------------------------------------------------------ demos
def build_demos(cfg: Config, store: Store, verdicts: Iterable[str] = ("candidate", "review"),
                limit: int | None = None, base_url: str = "", force: bool = False) -> dict:
    targets = [p for p in store.all()
               if p.verdict in verdicts and (force or not p.demo)]
    if limit:
        targets = targets[:limit]

    built = []
    for project in targets:
        meta = build_demo(project, project.screening or {}, project.proposal,
                          cfg.demo_dir, base_url=base_url)
        project.demo = meta
        if project.status in ("new", STATUS_SCREENED):
            project.status = STATUS_AWAITING if project.verdict == "candidate" else STATUS_SCREENED
        built.append(meta)
        print(f"  ✓ دمو ساخته شد: {project.title[:50]} → {meta['path']}")

    if built:
        from .pricing import propose
        for project in store.all():
            if project.demo and project.screening:
                project.proposal = propose(project, project.screening, cfg,
                                           demo_url=project.demo.get("url"))
        store.save()
        store.log("demo", "-", f"{len(built)} دمو ساخته شد")
    return {"built": len(built), "demos": built}


# ------------------------------------------------------------------ notify
def notify(cfg: Config, store: Store) -> dict:
    from .reporting import build_needs_you, write_report

    previous = {i["key"]: i for i in store.needs_you() if i.get("done")}
    needs = build_needs_you(store, cfg)
    for item in needs:
        if item["key"] in previous:
            item["done"] = True
            item["done_at"] = previous[item["key"]].get("done_at")
    store.set_needs_you(needs)

    report = write_report(store, cfg, needs)
    store.log("report", "-", report["path"])
    return {
        "report_path": report["path"],
        "needs_you": needs,
        "open_items": [i for i in needs if not i.get("done")],
    }


# ------------------------------------------------------------------ all
def run_all(cfg: Config, store: Store, offline: bool = True, refresh: bool = False,
            demo_limit: int | None = 3, base_url: str = "", force: bool = False,
            demo_verdicts: Iterable[str] = ("candidate",)) -> dict:
    print("— جمع‌آوری آگهی‌ها…")
    collected = collect(cfg, store, offline=offline, refresh=refresh)
    print(f"  {collected['fetched']} آگهی ({collected['new']} جدید)")

    print("— غربالگری (آیا در آرنا قابل اجراست؟)…")
    screened = screen_projects(cfg, store, force=force)
    print(f"  کاندیدا: {screened['counts'].get('candidate', 0)} | "
          f"بررسی: {screened['counts'].get('review', 0)} | "
          f"رد: {screened['counts'].get('rejected', 0)}")

    print("— ساخت دمو برای بهترین گزینه‌ها…")
    demos = build_demos(cfg, store, verdicts=demo_verdicts, limit=demo_limit,
                        base_url=base_url, force=force)

    print("— قیمت‌گذاری…")
    priced = price_projects(cfg, store, force=force)

    print("— گزارش و اعلان‌ها…")
    notified = notify(cfg, store)

    return {"collect": collected, "screen": screened, "demos": demos,
            "price": priced, "notify": notified}


def set_decision(store: Store, pid: str, decision: str, note: str | None = None) -> Project | None:
    project = store.get(pid)
    if not project:
        return None
    store.set_decision(pid, decision, note)
    if decision == "approved":
        project.status = STATUS_BUILT if project.demo else STATUS_AWAITING
    elif decision == "rejected":
        project.status = STATUS_REJECTED
    elif decision == "delivered":
        project.user_decision = "approved"
        project.status = STATUS_DELIVERED
    store.save()
    return project
