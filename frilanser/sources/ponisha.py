"""منبع پونیشا (ponisha.ir) — خواندن لیست پروژه‌ها از روی HTML/متن صفحه."""

from __future__ import annotations

import re

from ..normalize import (
    NUM,
    clean_text,
    parse_bids,
    parse_budget,
    parse_deadline_days,
    parse_duration_days,
)
from .base import BaseSource, after, before, merge_records, slice_blocks

CARD_RE = re.compile(r"\[([^\]]{5,200})\]\((https://ponisha\.ir/project/(\d+)/[^)\s]+)\)")


class PonishaSource(BaseSource):
    kind = "ponisha"
    label = "پونیشا"

    def parse(self, text: str) -> list[dict]:
        blocks = slice_blocks(text, CARD_RE)
        records: list[dict] = []
        for match, block in blocks:
            title = clean_text(match.group(1))
            url = match.group(2)
            external_id = match.group(3)

            desc_part = before(block, "مهارت ها", "فرصت انتخاب", "پیشنهادها", "* * *", "مشاهده‌ی پروژه")
            description = clean_text(desc_part)

            skills: list[str] = []
            if "مهارت ها" in block:
                skill_part = after(block, "مهارت ها")
                skill_part = before(skill_part, "فرصت انتخاب", "پیشنهادها", "* * *", "بودجه")
                for line in skill_part.splitlines():
                    line = clean_text(line)
                    if line and not line.startswith("http") and len(line) < 60:
                        skills.append(line)

            deadline = None
            m = re.search(r"فرصت انتخاب\s*([^\n]+)", block)
            if m:
                deadline = parse_deadline_days(m.group(1))
            if deadline is None:
                m = re.search(r"(\d+\s*روز(?:\s*و\s*\d+\s*ساعت)?)", block)
                if m:
                    deadline = parse_deadline_days(m.group(1))

            budget = parse_budget(block)
            bids = parse_bids(block)

            flags: list[str] = []
            if re.search(r"فوری", block):
                flags.append("فوری")
            if re.search(r"استخدام|همکاری مستمر|تمام وقت", block):
                flags.append("همکاری مستمر")

            records.append({
                "external_id": external_id,
                "title": title,
                "url": url,
                "description": description,
                "skills": skills,
                "budget_toman": budget,
                "client_deadline_days": deadline,
                "bids": bids,
                "posted_at": None,
                "location": None,
                "flags": flags,
            })
        return merge_records(records)


def project_url(project_id: str, slug: str = "") -> str:
    base = f"https://ponisha.ir/project/{project_id}/"
    return base + slug if slug else base
