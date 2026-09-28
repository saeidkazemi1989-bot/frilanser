"""مدل‌های داده‌ای برنامه."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from .normalize import clean_text

# وضعیت یک پروژه در خط لوله
STATUS_NEW = "new"                  # تازه پیدا شده
STATUS_SCREENED = "screened"        # غربال شده
STATUS_DEMO_READY = "demo_ready"    # دمو ساخته شده
STATUS_AWAITING = "awaiting"        # منتظر تصمیم شما
STATUS_APPROVED = "approved"        # تایید شده / در حال اجرا
STATUS_BUILT = "built"              # کار انجام شده، آماده تحویل
STATUS_DELIVERED = "delivered"      # تحویل داده شده
STATUS_REJECTED = "rejected"        # رد شده

STATUS_LABELS = {
    STATUS_NEW: "جدید",
    STATUS_SCREENED: "غربال‌شده",
    STATUS_DEMO_READY: "دمو آماده است",
    STATUS_AWAITING: "منتظر تصمیم شما",
    STATUS_APPROVED: "تایید‌شده (در حال اجرا)",
    STATUS_BUILT: "آماده‌ی تحویل",
    STATUS_DELIVERED: "تحویل‌شده",
    STATUS_REJECTED: "رد‌شده",
}

VERDICT_LABELS = {
    "candidate": "کاندیدای خوب",
    "review": "نیاز به بررسی",
    "rejected": "رد شده",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Project:
    id: str
    source: str
    external_id: str
    title: str
    url: str
    description: str = ""
    skills: list[str] = field(default_factory=list)
    budget_toman: int | None = None
    client_deadline_days: float | None = None
    posted_at: str | None = None
    bids: int | None = None
    location: str | None = None
    flags: list[str] = field(default_factory=list)
    status: str = STATUS_NEW
    first_seen: str = field(default_factory=now_iso)
    last_seen: str = field(default_factory=now_iso)
    screening: dict | None = None
    proposal: dict | None = None
    demo: dict | None = None
    user_decision: str | None = None     # approved | rejected | pending
    notes: list[str] = field(default_factory=list)

    # ---------- helpers ----------
    @property
    def verdict(self) -> str | None:
        return (self.screening or {}).get("verdict")

    @property
    def score(self) -> int:
        return int((self.screening or {}).get("score", 0))

    @property
    def source_label(self) -> str:
        return {"ponisha": "پونیشا", "karlancer": "کارلنسر",
                "karlancer_programming": "کارلنسر (برنامه‌نویسی)"}.get(self.source, self.source)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in data.items() if k in known}
        return cls(**clean)

    @classmethod
    def from_scrape(cls, source: str, external_id: str, title: str, url: str, **kwargs) -> "Project":
        return cls(
            id=f"{source}:{external_id}",
            source=source,
            external_id=str(external_id),
            title=clean_text(title),
            url=url,
            description=clean_text(kwargs.pop("description", "") or ""),
            **kwargs,
        )


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
