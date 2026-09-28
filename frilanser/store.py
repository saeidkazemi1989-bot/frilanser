"""ذخیره‌سازی ساده روی فایل JSON + صف کارهایی که باید توسط شما انجام شود."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import Project, STATUS_NEW, now_iso


class Store:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.projects_file = self.dir / "projects.json"
        self.needs_you_file = self.dir / "needs_you.json"
        self.activity_file = self.dir / "activity.json"
        self._projects: dict[str, Project] = {}
        self._load()

    # ---------------- persistence ----------------
    def _load(self) -> None:
        if self.projects_file.exists():
            try:
                raw = json.loads(self.projects_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                raw = {}
            for pid, data in raw.items():
                try:
                    self._projects[pid] = Project.from_dict(data)
                except TypeError:
                    continue

    def save(self) -> None:
        payload = {pid: p.to_dict() for pid, p in self._projects.items()}
        self.projects_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )

    # ---------------- projects ----------------
    @property
    def projects(self) -> dict[str, Project]:
        return self._projects

    def upsert(self, project: Project) -> tuple[Project, bool]:
        """درج یا به‌روزرسانی؛ خروجی (پروژه، آیا جدید بود)."""
        existing = self._projects.get(project.id)
        if existing is None:
            project.status = project.status or STATUS_NEW
            self._projects[project.id] = project
            self.log("new", project.id, project.title[:80])
            return project, True

        # داده‌های متنی را به‌روز می‌کنیم اما وضعیت/تصمیم کاربر را نگه می‌داریم
        existing.title = project.title or existing.title
        existing.description = project.description or existing.description
        existing.url = project.url or existing.url
        existing.skills = project.skills or existing.skills
        existing.budget_toman = project.budget_toman or existing.budget_toman
        existing.client_deadline_days = project.client_deadline_days or existing.client_deadline_days
        existing.posted_at = project.posted_at or existing.posted_at
        existing.bids = project.bids if project.bids is not None else existing.bids
        existing.location = project.location or existing.location
        existing.flags = project.flags or existing.flags
        existing.last_seen = now_iso()
        if existing.status in (STATUS_NEW,):
            existing.status = project.status
        return existing, False

    def upsert_many(self, projects: Iterable[Project]) -> tuple[int, int]:
        new = updated = 0
        for p in projects:
            _, is_new = self.upsert(p)
            new, updated = (new + 1, updated) if is_new else (new, updated + 1)
        self.save()
        return new, updated

    def get(self, pid: str) -> Project | None:
        return self._projects.get(pid)

    def all(self) -> list[Project]:
        return sorted(
            self._projects.values(),
            key=lambda p: (p.score, p.budget_toman or 0),
            reverse=True,
        )

    def by_verdict(self, verdict: str) -> list[Project]:
        return [p for p in self.all() if p.verdict == verdict]

    def set_status(self, pid: str, status: str, note: str | None = None) -> Project | None:
        p = self._projects.get(pid)
        if not p:
            return None
        p.status = status
        if note:
            p.notes.append(f"[{now_iso()[:16]}] {note}")
        self.log(status, pid, note or "")
        self.save()
        return p

    def set_decision(self, pid: str, decision: str, note: str | None = None) -> Project | None:
        p = self._projects.get(pid)
        if not p:
            return None
        p.user_decision = decision
        if note:
            p.notes.append(f"[{now_iso()[:16]}] {note}")
        self.log(f"decision:{decision}", pid, note or "")
        self.save()
        return p

    # ---------------- needs you ----------------
    def needs_you(self) -> list[dict]:
        if not self.needs_you_file.exists():
            return []
        try:
            return json.loads(self.needs_you_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def set_needs_you(self, items: list[dict]) -> None:
        self.needs_you_file.write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def open_needs_you(self) -> list[dict]:
        return [i for i in self.needs_you() if not i.get("done")]

    def complete_needs_you(self, key: str) -> bool:
        items = self.needs_you()
        changed = False
        for item in items:
            if item.get("key") == key and not item.get("done"):
                item["done"] = True
                item["done_at"] = now_iso()
                changed = True
        if changed:
            self.set_needs_you(items)
        return changed

    # ---------------- activity ----------------
    def log(self, action: str, pid: str, detail: str = "") -> None:
        entries: list[dict] = []
        if self.activity_file.exists():
            try:
                entries = json.loads(self.activity_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                entries = []
        entries.append({"at": now_iso(), "action": action, "project": pid, "detail": detail})
        self.activity_file.write_text(
            json.dumps(entries[-500:], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def activity(self, limit: int = 30) -> list[dict]:
        if not self.activity_file.exists():
            return []
        try:
            entries = json.loads(self.activity_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return list(reversed(entries[-limit:]))
