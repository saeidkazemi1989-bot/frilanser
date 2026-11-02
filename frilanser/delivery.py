"""اجرای پروژه‌ی تاییدشده: ساخت، بسته‌بندی و آماده‌سازیِ تحویل.

وقتی شما روی یک آگهی «تایید — کار را انجام بده» می‌زنید، این ماژول کار می‌کند:

۱. اگر پروژه هنوز غربال/قیمت‌گذاری نشده باشد، آن را انجام می‌دهد؛
۲. یک **پیش‌نمایشِ قفل‌شده** برای کارفرما می‌سازد (همان چیزی که در دمو می‌بینید)؛
۳. **کدِ منبعِ واقعی** پروژه را می‌سازد (پروژه‌ی Vite + React + Tailwind، قابلِ
   اجرا با `npm install && npm run dev`)؛
۴. همه را در یک پوشه‌ی تحویل بسته‌بندی می‌کند به همراهِ:
   - «تحویل.md»: چی ساخته شده و چطور اجرا می‌شود؛
   - «کاربرگِ اجرا.md»: برگه‌ای که می‌توانید به یک برنامه‌نویس (یا به آرنا)
     بدهید تا منطقِ اختصاصیِ پروژه را روی همین اسکلت بنویسد؛
   - «پیامِ تحویل.txt»: متنِ آماده برای فرستادن به کارفرما؛
۵. وضعیت را به «آماده‌ی تحویل» می‌برد و کارهای باقی‌مانده را در
   «نیاز به ورود شما» ثبت می‌کند.

**صداقت مهم است:** این ابزار اسکلت و رابطِ کار را می‌سازد، اما منطقِ اختصاصیِ
هر سفارش (مثلاً «محتوای ۱۵۰ کتاب را استخراج کن») را خودبه‌خود نمی‌نویسد. برای
همین در خروجی دقیقاً نوشته شده چه چیزی آماده است و چه چیزی هنوز کارِ انسانی
می‌خواهد — تا هیچ‌وقت فکر نکنید «انجام شد» در حالی که چیزی ساخته نشده.
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from .models import (
    STATUS_BUILT,
    STATUS_DELIVERED,
    STATUS_REJECTED,
    Project,
    now_iso,
)

DELIVERY_DIRNAME = "deliveries"


def _slug(project: Project) -> str:
    base = f"{project.source}-{project.external_id}"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-").lower()
    return slug or "project"


def delivery_dir(cfg, project: Project) -> Path:
    d = Path(cfg.outbox_dir) / DELIVERY_DIRNAME / _slug(project)
    d.mkdir(parents=True, exist_ok=True)
    return d


# --------------------------------------------------------------------------- #
# محتوای فایل‌های همراه
# --------------------------------------------------------------------------- #
def _readme_text(project: Project, steps: list[dict], files: list[dict],
                 checklist: list[str]) -> str:
    lines = [
        f"# بسته‌ی تحویل — {project.title}",
        "",
        f"ساخته‌شده: {time.strftime('%Y-%m-%d %H:%M')}",
        f"منبعِ آگهی: {project.source_label}",
        f"نشانیِ آگهی: {project.url or '—'}",
        "",
        "## این بسته چیست",
        "",
    ]
    for s in steps:
        mark = "✓" if s["ok"] else "✗"
        lines.append(f"- {mark} {s['label']} — {s['detail']}")
    lines += ["", "## فایل‌ها", ""]
    for f in files:
        lines.append(f"- `{f['name']}` ({f['size']:,} بایت) — {f['note']}")
    if project.proposal:
        lines += [
            "",
            "## قیمت و زمان",
            "",
            f"- قیمتِ توافق‌شده: {project.proposal.get('price', 0):,} تومان",
            f"- زمانِ برآوردی: {project.proposal.get('hours', 0)} ساعت",
        ]
        ms = project.proposal.get("milestones") or []
        if ms:
            lines.append("")
            lines.append("## برنامه‌ی پرداخت")
            lines.append("")
            for m in ms:
                lines.append(f"- {m.get('title')} — {int((m.get('share') or 0) * 100)}٪ ({m.get('when', '')})")
    if checklist:
        lines += ["", "## چه کارهایی مانده (با خودِ شما)", ""]
        for c in checklist:
            lines.append(f"- [ ] {c}")
    lines += [
        "",
        "## چطور اجرا می‌شود",
        "",
        "پروژه‌ی اصلی در پوشه‌ی `source/` است و با Vite + React + Tailwind ساخته شده:",
        "",
        "```bash",
        "cd source",
        "npm install",
        "npm run dev     # برای دیدن روی کامپیوتر خودتان",
        "npm run build   # برای ساختِ نسخه‌ی نهایی (خروجی در dist/)",
        "```",
        "",
        "فایل `پیش‌نمایش-برای-کارفرما.html` را هم می‌توانید مستقیم با مرورگر باز",
        "کنید؛ قفل است و کارفرما فقط آن را می‌بیند، نمی‌تواند استفاده‌اش کند.",
        "",
    ]
    return "\n".join(lines)


def _brief_text(project: Project, checklist: list[str]) -> str:
    """برگه‌ای برای دادن به برنامه‌نویس (یا به آرنا) تا کارِ اختصاصی را انجام دهد."""
    lines = [
        f"# کاربرگِ اجرا — {project.title}",
        "",
        "این برگه را به برنامه‌نویس بدهید (یا در آرنا برای من بفرستید) تا منطقِ",
        "اختصاصیِ پروژه را روی اسکلتِ آماده بنویسد.",
        "",
        "## متنِ کاملِ آگهی",
        "",
        project.description or "(متنی در آگهی نبود)",
        "",
        "## مهارت‌های خواسته‌شده",
        "",
        ", ".join(project.skills or []) or "—",
        "",
    ]
    if project.budget_toman:
        lines += [f"## بودجه‌ی کارفرما: {project.budget_toman:,} تومان", ""]
    if project.client_deadline_days:
        lines += [f"## مهلت: {project.client_deadline_days} روز", ""]
    if project.proposal:
        lines += [
            "## توافقِ ما",
            "",
            f"- مبلغ: {project.proposal.get('price', 0):,} تومان",
            f"- زمان: {project.proposal.get('hours', 0)} ساعت",
            "",
        ]
    if project.attachments:
        lines += ["## پیوست‌های کارفرما", ""]
        for a in project.attachments:
            lines.append(f"- {a.get('name')} ({a.get('size', 0):,} بایت){' — ' + a['note'] if a.get('note') else ''}")
        lines.append("")
    if project.attachment_links:
        lines += ["## پیوندهای فایل در آگهی", ""]
        for a in project.attachment_links:
            lines.append(f"- {a.get('url')}")
        lines.append("")
    scr = project.screening or {}
    if scr.get("needs_you"):
        lines += ["## نکاتی که از متنِ آگهی فهمیده شده", ""]
        for n in scr["needs_you"]:
            lines.append(f"- {n.get('kind')}: {n.get('text')}")
        lines.append("")
    lines += [
        "## تحلیلِ برنامه",
        "",
        f"- امتیازِ اجراپذیری: {scr.get('score', '—')}/۱۰۰",
        f"- دسته: {scr.get('category_label', '—')}",
        f"- زمانِ برآوردی: {scr.get('est_hours', '—')} ساعت",
        "",
    ]
    lines += [
        "## چه مانده است",
        "",
    ]
    for c in checklist:
        lines.append(f"- {c}")
    lines += ["", "## اسکلتِ آماده", "",
              "پوشه‌ی `source/` شکل و ظاهر و ساختارِ پروژه است (صفحه‌ها، منو،",
              "رنگ‌بندی، واکنش‌گرایی). منطقِ واقعی باید روی آن نوشته شود.", ""]
    return "\n".join(lines)


def _message_text(project: Project, checklist: list[str]) -> str:
    """متنِ آماده برای فرستادن به کارفرما."""
    price = (project.proposal or {}).get("price", 0)
    hours = (project.proposal or {}).get("hours", 0)
    return "\n".join([
        f"سلام، در مورد «{project.title}»:",
        "",
        "نسخه‌ی اولیه آماده است و بخشی از کار را می‌توانید ببینید.",
        "پیش‌نمایش را برایتان فرستادم تا شکل و ظاهر و بخش‌های اصلی را ببینید.",
        "",
        f"- زمانِ صرف‌شده تا این مرحله: حدود {hours} ساعت"
        + (f" · مبلغِ توافق‌شده: {price:,} تومان" if price else ""),
        "",
        "پیش از تحویلِ نهایی این موارد را با هم قطعی می‌کنیم:",
        "",
    ] + [f"{i+1}) {c}" for i, c in enumerate(checklist[:6])] + [
        "",
        "هر کدام را تأیید کنید تا نسخه‌ی نهایی را تحویل بدهم.",
        "اگر نکته‌ای هست که باید تغییر کند، همین‌جا بگویید تا در نسخه‌ی بعدی",
        "لحاظ شود.",
        "",
        "با احترام",
    ])


# --------------------------------------------------------------------------- #
# اجرای اصلی
# --------------------------------------------------------------------------- #
def do_work(cfg, store, pid: str, base_url: str = "") -> dict:
    """پروژه را واقعاً پیش می‌برد. خروجی: گزارشِ کامل برای نمایش به کاربر."""
    project = store.get(pid)
    if project is None:
        return {"ok": False, "error": "این آگهی پیدا نشد", "steps": [], "files": [],
                "checklist": []}

    steps: list[dict] = []

    def step(label: str, ok: bool, detail: str) -> None:
        steps.append({"label": label, "ok": bool(ok), "detail": detail})

    # ۱) غربال و قیمت‌گذاری (اگر انجام نشده)
    try:
        from .pipeline import price_projects, screen_projects

        if not project.screening:
            screen_projects(cfg, store, force=True)
            project = store.get(pid) or project
            step("غربالگری", bool(project.screening), "آیا این کار در آرنا قابل اجراست؟")
        if not project.proposal:
            price_projects(cfg, store, force=True)
            project = store.get(pid) or project
            step("قیمت‌گذاری", bool(project.proposal),
                 f"{project.proposal.get('price', 0):,} تومان" if project.proposal else "ناموفق")
    except Exception as exc:  # noqa: BLE001
        step("غربال/قیمت‌گذاری", False, f"خطا: {exc}")

    d = delivery_dir(cfg, project)

    # ۲) پیش‌نمایشِ قفل‌شده برای کارفرما
    preview_rel = ""
    try:
        from .demo_builder import build_demo

        meta = build_demo(project, project.screening or {}, project.proposal,
                          cfg.demo_dir, base_url=base_url)
        project.demo = meta
        src_client = Path(cfg.demo_dir) / meta["client_rel"]
        if src_client.exists():
            target = d / "پیش‌نمایش-برای-کارفرما.html"
            shutil.copy2(src_client, target)
            preview_rel = "پیش‌نمایش-برای-کارفرما.html"
        step("پیش‌نمایشِ کارفرما", True,
             "فایلی که کارفرما می‌بیند (قفل‌شده، قابل استفاده نیست)")
    except Exception as exc:  # noqa: BLE001
        step("پیش‌نمایشِ کارفرما", False, f"خطا: {exc}")

    # ۳) کدِ منبعِ واقعی
    source_ok = False
    try:
        from .react_builder import build_react_project

        rmeta = build_react_project(project, project.screening or {}, project.proposal,
                                    Path(cfg.react_dir))
        src_root = Path(rmeta["path"])
        dest = d / "source"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src_root, dest)
        n = len([f for f in dest.rglob("*") if f.is_file()])
        source_ok = True
        step("کدِ منبعِ پروژه", True,
             f"{n} فایل (Vite + React + Tailwind) در پوشه‌ی source/")
    except Exception as exc:  # noqa: BLE001
        step("کدِ منبعِ پروژه", False, f"خطا: {exc}")

    # ۴) چک‌لیستِ کارهای باقی‌مانده
    checklist: list[str] = []
    scr = project.screening or {}
    for n in (scr.get("needs_you") or [])[:5]:
        checklist.append(f"{n.get('text')} ({n.get('kind', '')})".strip())
    checklist.append("منطقِ اختصاصیِ پروژه روی اسکلتِ آماده نوشته شود "
                     "(کاربرگِ اجرا را به برنامه‌نویس یا به آرنا بدهید)")
    if project.attachment_links:
        checklist.append("فایل‌های پیوندشده در آگهی از سایت دریافت شود")
    checklist.append("نسخه‌ی نهایی ساخته و روی هاست/سرورِ کارفرما بالا برده شود")
    checklist.append("تحویلِ نهایی به کارفرما (با خودِ شماست)")

    # ۵) نوشتنِ فایل‌های همراه
    files: list[dict] = []
    written = {
        "تحویل.md": _readme_text(project, steps, [], checklist),
        "کاربرگِ اجرا.md": _brief_text(project, checklist),
        "پیامِ تحویل.txt": _message_text(project, checklist),
    }
    for name, text in written.items():
        try:
            (d / name).write_text(text, encoding="utf-8")
        except OSError:
            continue

    # ۶) فهرستِ فایل‌ها برای نمایش
    for f in sorted(d.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(d)).replace("\\", "/")
        if rel.startswith("source/") and rel.count("/") > 1:
            note = "از کدِ منبع"
        elif rel.startswith("source/"):
            note = "کدِ منبع"
        elif rel == preview_rel:
            note = "برای فرستادن به کارفرما (قفل‌شده)"
        else:
            note = "راهنما"
        files.append({"name": rel, "rel": str(f.relative_to(Path(cfg.outbox_dir))).replace("\\", "/"),
                      "size": f.stat().st_size, "note": note})

    # فایلِ تحویل.md را دوباره با فهرستِ کامل می‌نویسیم
    try:
        (d / "تحویل.md").write_text(
            _readme_text(project, steps, files, checklist), encoding="utf-8")
    except OSError:
        pass

    # ۷) وضعیت و یادداشت
    project.status = STATUS_BUILT
    project.user_decision = "approved"
    project.delivery = {
        "built_at": time.strftime("%Y-%m-%d %H:%M"),
        "dir": str(d),
        "slug": _slug(project),
        "steps": steps,
        "files": files,
        "checklist": checklist,
        "message": _message_text(project, checklist),
        "preview": preview_rel,
        "has_source": source_ok,
    }
    project.history.append(f"{now_iso()[:16]} — اجرا آغاز شد و بسته‌ی تحویل ساخته شد")
    project.notes.append(f"بسته‌ی تحویل ساخته شد: {d}")

    # ۸) ثبت در «نیاز به ورود شما»
    try:
        items = store.needs_you()
        keys = {i.get("key") for i in items}
        key = f"{project.id}:deliver"
        if key not in keys:
            items.append({
                "key": key,
                "project_id": project.id,
                "project_title": project.title,
                "source": project.source_label,
                "kind": "deliver",
                "kind_label": "تحویلِ نهایی پروژه",
                "how": "بسته‌ی تحویل آماده است؛ بعد از قطعی کردنِ مواردِ چک‌لیست، "
                       "نسخه‌ی نهایی را برای کارفرما بفرستید.",
                "text": f"بسته‌ی تحویلِ «{project.title}» ساخته شد. "
                        f"منطقِ اختصاصی را تکمیل و سپس تحویل دهید.",
                "url": project.url or "",
                "done": False,
                "created_at": now_iso(),
            })
            store.set_needs_you(items)
    except Exception:  # noqa: BLE001
        pass

    store.upsert_many([project])
    store.save()
    store.snapshot(force=True)

    return {
        "ok": source_ok or bool(preview_rel),
        "steps": steps,
        "files": files,
        "checklist": checklist,
        "dir": str(d),
        "message": project.delivery["message"],
    }


def client_html_rel(project: Project) -> str | None:
    d = (project.delivery or {})
    return d.get("preview") or None
