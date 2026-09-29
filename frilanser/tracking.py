"""به‌روزرسانیِ وضعیتِ پروژه‌ها بر اساسِ اسکن‌های پیاپی.

هدف: اگر روی پروژه‌ای پیشنهاد داده باشید، وضعیتش در به‌روزرسانی‌های بعدی
**گم نشود**؛ و اگر پروژه از فهرست سایت حذف شود یا نشانه‌ی «واگذار شد» پیدا شود،
خودِ برنامه آن را تشخیص بدهد و به شما خبر بدهد.
"""

from __future__ import annotations

from .models import PROPOSAL_STATES, Project

#: نشانه‌های متنیِ اینکه پروژه دیگر قابل پیشنهاد دادن نیست
CLOSED_MARKERS = (
    "واگذار شد", "واگذار گردید", "اختصاص یافت", "انتخاب فریلنسر",
    "بسته شد", "بسته شده", "منقضی شده", "منقضی", "پایان یافته", "اتمام یافته",
    "لغو شد", "حذف شده",
)
# نشانه‌هایی که در میانِ جمله‌های معمولی هم می‌آیند و نباید مبنا قرار گیرند
# (مثل «تکمیل فایل اکسل» که نباید با «تکمیل شد» اشتباه گرفته شود)
AMBIGUOUS = ("تکمیل شد",)


def looks_closed(project: Project) -> str | None:
    """اگر نشانه‌ی بسته/واگذار شدن در متن آگهی باشد، نام آن نشانه را برمی‌گرداند."""
    text = f"{project.title or ''} {project.description or ''} {' '.join(project.flags or [])}"
    low = str(text).lower()
    for marker in CLOSED_MARKERS:
        if marker in low:
            return marker
    # نشانه‌های مبهم: فقط اگر در انتهای جمله/متن آمده باشند
    for marker in AMBIGUOUS:
        if low.rstrip().endswith(marker) or f"{marker}." in low or f"{marker} " == low[-len(marker) - 1:]:
            return marker
    return None


def apply_scan_results(store, seen_ids, threshold: int = 2) -> dict:
    """پس از هر اسکن: شمارنده‌ی «دیده نشدن» را به‌روزرسانی و وضعیت‌ها را اصلاح می‌کند.

    - پروژه‌ای که در اسکن دیده شود: شمارنده صفر می‌شود.
    - پروژه‌ای که پیشنهاد داده شده و `threshold` بار پیاپی دیده نشود: «واگذار/بسته شد».
    - پروژه‌ای که در متنش نشانه‌ی بسته شدن باشد: همان‌جا «واگذار/بسته شد».

    وضعیت‌های دستیِ کاربر («گرفتم» / «نگرفتم») هرگز تغییر نمی‌کنند.
    """
    closed_by_miss = store.mark_missed(seen_ids, threshold=threshold)

    closed_by_text: list[Project] = []
    for project in store.all():
        if project.proposal_state in ("won", "lost"):
            continue
        marker = looks_closed(project)
        if marker and project.proposal_state != "closed":
            project.proposal_state = "closed"
            project.history = (project.history or []) + [
                f"در متن آگهی نشانه‌ی «{marker}» پیدا شد"
            ]
            closed_by_text.append(project)

    if closed_by_text:
        store.save()
        for p in closed_by_text:
            store.log("auto_close", p.id, f"نشانه‌ی متنی: {p.title[:60]}")

    return {
        "closed_by_miss": [p.id for p in closed_by_miss],
        "closed_by_text": [p.id for p in closed_by_text],
        "kept": sum(1 for p in store.all()
                    if p.proposal_state in ("submitted", "won")),
    }


def state_summary(store) -> dict:
    """خلاصه‌ی وضعیتِ پیشنهادها (برای نمایش در گزارش و داشبورد)."""
    counts: dict[str, int] = {key: 0 for key in PROPOSAL_STATES}
    for p in store.all():
        counts[p.proposal_state] = counts.get(p.proposal_state, 0) + 1
    return {"counts": counts,
            "active": sum(1 for p in store.all() if p.proposal_state == "submitted"),
            "won": sum(1 for p in store.all() if p.proposal_state == "won")}
