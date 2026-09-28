"""گزارش‌گیری و ساخت صف «کارهایی که باید خودتان انجام دهید»."""

from __future__ import annotations

from datetime import datetime

from .config import Config
from .models import Project, STATUS_BUILT
from .store import Store

VERDICT_ORDER = {"candidate": 0, "review": 1, "rejected": 2}

KIND_LABELS = {
    "approve": "تایید پروژه (پس از پذیرش کارفرما)",
    "submit_proposal": "ثبت پیشنهاد در سایت",
    "provide_access": "گرفتن دسترسی / اطلاعات از کارفرما",
    "delivery_format": "توافق روی شکل تحویل",
    "deliver": "تحویل پروژه در سایت",
}

KIND_HOWTO = {
    "submit_proposal": "وارد آگهی شوید، متن پیشنهادِ آماده را کپی کنید و در بخش ثبت پیشنهاد بفرستید.",
    "approve": "اگر کارفرما پیشنهاد را پذیرفت، در داشبورد یا با دستور approve تایید کنید تا اجرا شروع شود.",
    "provide_access": "از کارفرما بخواهید دسترسی‌های لیست‌شده را بفرستد و آن‌ها را در اختیار آرنا قرار دهید.",
    "delivery_format": "با کارفرما درباره‌ی شکل تحویل (مثلاً سایت اختصاصی در برابر قالب وردپرس) به توافق برسید.",
    "deliver": "فایل‌های نهایی را در صفحه‌ی پروژه بارگذاری کنید و تحویل را ثبت کنید.",
}


def build_needs_you(store: Store, cfg: Config) -> list[dict]:
    """فهرست کارهایی که فقط خودِ شما باید انجام دهید.

    منطقِ صف:
      - برای کاندیداهایی که ارزشِ ارسال پیشنهاد دارند → «ثبت پیشنهاد در سایت»
      - بعد از اینکه ثبت پیشنهاد را تیک زدید → «تایید پروژه» ظاهر می‌شود
      - پروژه‌های نیازمند دسترسی/توافق روی تحویل → یک کار جداگانه
      - پروژه‌های آماده → «تحویل در سایت»
    """
    items: list[dict] = []
    now = datetime.now().isoformat(timespec="seconds")
    previous = {i["key"]: i for i in store.needs_you()}

    for project in store.all():
        screening = project.screening or {}
        proposal = project.proposal or {}

        if project.user_decision == "approved" or project.status == STATUS_BUILT:
            items.append(_item(
                project, "deliver",
                "پروژه آماده‌ی تحویل است؛ خروجی‌ها را در سایت بارگذاری و تحویل را ثبت کنید.",
                now,
            ))

        if project.user_decision == "rejected" or project.verdict == "rejected":
            continue

        worth_proposing = _worth_proposing(project, proposal)

        if worth_proposing:
            items.append(_item(
                project, "submit_proposal",
                "متن پیشنهاد و دموی این پروژه آماده است؛ آن را در سایتِ فریلنسری روی همین آگهی ثبت کنید.",
                now,
            ))

        for need in screening.get("needs_you", []):
            kind = need.get("kind", "approve")

            if kind == "submit_proposal":
                if not worth_proposing:
                    continue
            if kind == "approve":
                # فقط بعد از اینکه پیشنهاد را در سایت ثبت کردید
                submitted = previous.get(f"{project.id}:submit_proposal", {}).get("done")
                if project.verdict != "candidate" or not submitted:
                    continue
                continue_ = need.get("text", "")
                items.append(_item(project, kind, continue_, now))
                continue

            items.append(_item(project, kind, need.get("text", ""), now))

        # اگر کارفرما پیشنهاد را پذیرفت، تایید نهایی برای شروع اجرا
        if worth_proposing and project.demo:
            submitted = previous.get(f"{project.id}:submit_proposal", {}).get("done")
            if submitted and project.user_decision != "approved":
                items.append(_item(
                    project, "approve",
                    "پیشنهاد را ثبت کرده‌اید. اگر کارفرما پذیرفت، تایید کنید تا اجرا و تحویل در آرنا شروع شود.",
                    now,
                ))

    # حذف موارد تکراری
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        if item["key"] in seen:
            continue
        seen.add(item["key"])
        unique.append(item)

    order = {"deliver": 0, "submit_proposal": 1, "provide_access": 2,
             "delivery_format": 3, "approve": 4}
    unique.sort(key=lambda i: (order.get(i["kind"], 9), -(i.get("price") or 0)))
    return unique


def _worth_proposing(project: Project, proposal: dict) -> bool:
    """آیا ارزش دارد برای این پروژه پیشنهاد بفرستیم؟"""
    if project.verdict != "candidate":
        return False
    if project.user_decision == "rejected":
        return False
    ratio = proposal.get("budget_ratio")
    if ratio is not None and ratio < 0.75:
        return False  # بودجه خیلی کمتر از برآورد — صرف نمی‌کند
    return True


def _item(project: Project, kind: str, text: str, now: str) -> dict:
    proposal = project.proposal or {}
    return {
        "key": f"{project.id}:{kind}",
        "project_id": project.id,
        "project_title": project.title,
        "source": project.source_label,
        "kind": kind,
        "kind_label": KIND_LABELS.get(kind, kind),
        "how": KIND_HOWTO.get(kind, ""),
        "text": text,
        "url": project.url,
        "demo_url": (project.demo or {}).get("url"),
        "price": proposal.get("price"),
        "budget": project.budget_toman,
        "proposal_text": proposal.get("proposal_text"),
        "done": False,
        "created_at": now,
    }


def markdown_report(store: Store, cfg: Config, needs_you: list[dict]) -> str:
    projects = store.all()
    candidates = [p for p in projects if p.verdict == "candidate"]
    reviews = [p for p in projects if p.verdict == "review"]
    rejected = [p for p in projects if p.verdict == "rejected"]

    total_budget = sum(p.budget_toman or 0 for p in candidates)
    total_price = sum((p.proposal or {}).get("price", 0) or 0 for p in candidates)
    total_hours = sum((p.screening or {}).get("est_hours", 0) for p in candidates)

    now = datetime.now()
    lines = [
        f"# گزارش فریلنس‌یار آرنا",
        f"",
        f"**تاریخ:** {now.strftime('%Y/%m/%d %H:%M')}  ",
        f"**تعداد آگهی‌های بررسی‌شده:** {len(projects)}  ",
        f"**منابع:** "
        + "، ".join(sorted({p.source_label for p in projects}) or ["—"]),
        "",
        "## خلاصه",
        "",
        "| شاخص | مقدار |",
        "| --- | --- |",
        f"| کاندیدای خوب (قابل اجرا در آرنا) | {len(candidates)} |",
        f"| نیاز به بررسی | {len(reviews)} |",
        f"| رد شده | {len(rejected)} |",
        f"| مجموع بودجه‌ی کاندیداها | {total_budget:,} تومان |",
        f"| مجموع قیمت پیشنهادی ما | {total_price:,} تومان |",
        f"| مجموع زمان برآوردی | {total_hours:g} ساعت |",
        "",
    ]

    if candidates:
        lines += ["## ⭐ پروژه‌های کاندید (به ترتیب اولویت)", ""]
        for i, p in enumerate(sorted(candidates, key=lambda x: -x.score), 1):
            lines.append(_project_block(i, p, detailed=True))
        lines.append("")

    if reviews:
        lines += ["## پروژه‌های نیازمند بررسی", ""]
        for i, p in enumerate(sorted(reviews, key=lambda x: -x.score), 1):
            lines.append(_project_block(i, p, detailed=False))
        lines.append("")

    if rejected:
        lines += ["## رد شده‌ها", ""]
        lines.append("| # | پروژه | منبع | بودجه | دلیل اصلی |")
        lines.append("| --- | --- | --- | --- | --- |")
        for i, p in enumerate(sorted(rejected, key=lambda x: -x.score), 1):
            reason = _top_reason(p)
            budget = f"{p.budget_toman:,}" if p.budget_toman else "—"
            lines.append(
                f"| {i} | [{p.title[:60]}]({p.url}) | {p.source_label} | {budget} | {reason} |"
            )
        lines.append("")

    if needs_you:
        open_items = [i for i in needs_you if not i.get("done")]
        lines += [f"## 🔔 کارهایی که باید خودتان انجام دهید ({len(open_items)} مورد)", ""]
        for i, item in enumerate(open_items, 1):
            lines += [
                f"### {i}. {item['kind_label']} — {item['project_title'][:70]}",
                f"- **چه کاری:** {item['text']}",
                f"- **چطور:** {item['how']}",
            ]
            if item.get("price"):
                lines.append(f"- **مبلغ پیشنهادی:** {item['price']:,} تومان")
            if item.get("url"):
                lines.append(f"- **لینک آگهی:** {item['url']}")
            if item.get("demo_url"):
                lines.append(f"- **دمو:** {item['demo_url']}")
            lines.append("")

    lines += [
        "---",
        "",
        "_این گزارش به‌صورت خودکار توسط «فریلنس‌یار آرنا» ساخته شده است. "
        "ثبت پیشنهاد در سایت و تحویل نهایی پروژه توسط خود شما انجام می‌شود._",
    ]
    return "\n".join(lines)


def _top_reason(project: Project) -> str:
    screening = project.screening or {}
    if screening.get("blockers"):
        return screening["blockers"][0]
    negatives = [r for r in screening.get("reasons", []) if r.get("impact", 0) < 0]
    if negatives:
        return min(negatives, key=lambda r: r["impact"])["text"]
    return screening.get("category_label", "—")


def _project_block(index: int, project: Project, detailed: bool) -> str:
    screening = project.screening or {}
    proposal = project.proposal or {}
    budget = f"{project.budget_toman:,} تومان" if project.budget_toman else "اعلام نشده"
    price = f"{proposal.get('price', 0):,} تومان" if proposal.get("price") else "—"

    lines = [
        f"### {index}. {project.title}",
        f"- **منبع:** {project.source_label} — [مشاهده آگهی]({project.url})",
        f"- **دسته:** {screening.get('category_label', '—')} | "
        f"**امتیاز اجراپذیری:** {screening.get('score', 0)}/100",
        f"- **بودجه کارفرما:** {budget} | **قیمت پیشنهادی ما:** {price}",
        f"- **زمان اجرا:** {screening.get('est_hours', '—')} ساعت "
        f"(حدود {screening.get('schedule_days', '—')} روز کاری)",
    ]
    if proposal.get("budget_verdict"):
        verdict_fa = {
            "excellent": "بودجه عالی (بالاتر از برآورد)",
            "good": "بودجه مناسب",
            "ok": "بودجه هم‌خوان",
            "negotiate": "بودجه کمتر از برآورد — نیاز به مذاکره",
            "low": "بودجه خیلی کم است",
            "unknown": "بودجه نامشخص",
        }[proposal["budget_verdict"]]
        lines.append(f"- **وضعیت بودجه:** {verdict_fa}")
    if project.demo:
        lines.append(f"- **دموی ساخته‌شده:** {project.demo.get('url')}")

    if detailed:
        lines.append("")
        lines.append("**دلایل انتخاب:**")
        for reason in screening.get("reasons", [])[:8]:
            sign = "+" if reason.get("impact", 0) > 0 else ("-" if reason.get("impact", 0) < 0 else "•")
            lines.append(f"- `{sign}` {reason['text']}")
        if screening.get("needs_you"):
            lines.append("")
            lines.append("**نیاز به ورود شما:**")
            for need in screening["needs_you"]:
                lines.append(f"- {need['text']}")
        if proposal.get("proposal_text"):
            lines += [
                "",
                "<details><summary>متن پیشنهاد آماده برای ثبت در سایت</summary>",
                "",
                "```text",
                proposal["proposal_text"],
                "```",
                "",
                "</details>",
            ]
    lines.append("")
    return "\n".join(lines)


def write_report(store: Store, cfg: Config, needs_you: list[dict]) -> dict:
    text = markdown_report(store, cfg, needs_you)
    cfg.report_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.report_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    path.write_text(text, encoding="utf-8")
    latest = cfg.report_dir / "latest.md"
    latest.write_text(text, encoding="utf-8")
    return {"path": str(path), "latest": str(latest), "text": text}
