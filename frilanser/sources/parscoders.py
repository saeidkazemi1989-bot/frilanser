"""منبع پارس‌کدرز (parscoders.com) — خواندن فهرست پروژه‌ها."""

from __future__ import annotations

import re

from ..normalize import clean_text, parse_bids, parse_budget, parse_posted_at
from .base import BaseSource, merge_records, slice_blocks

# کارت‌ها به شکل «###### [عنوان](آدرس پروژه)» هستند
CARD_RE = re.compile(
    r"######\s*\[([^\]]{3,200})\]\((https://parscoders\.com/project/(\d+)(?:/[^)\s]*)?)\)"
)
SKILL_RE = re.compile(r"\[([^\]]{2,60})\]\(https://parscoders\.com/project/skills/[^)]+\)")
BUDGET_RE = re.compile(r"حداکثر بودجه:\s*([^\n]+)")
# زمان انتشار همیشه در یک خط مستقل است (مثل «پنجاه دقیقه پیش»).
# لنگر ^ جلوی اشتباه گرفتن عباراتی مثل «ارسال پیشنهاد» را می‌گیرد.
TIME_RE = re.compile(r"(?m)^([^\n]{0,40}?(?:دقیقه|ساعت|روز|هفته|ماه|سال)\s+پیش)")
BIDS_RE = re.compile(r"با\s*(\d+)\s*پیشنهاد")

FLAG_WORDS = ("فوری", "خصوصی", "مخفی", "پروژه ویژه", "آگهی استخدام", "پاداش")


class ParsCodersSource(BaseSource):
    kind = "parscoders"
    label = "پارس‌کدرز"

    def parse(self, text: str) -> list[dict]:
        blocks = slice_blocks(text, CARD_RE)
        records: list[dict] = []
        for match, block in blocks:
            title = clean_text(match.group(1))
            # بعضی عنوان‌ها با کد پروژه شروع می‌شوند: «118248 - ادیت کیلیپ»
            title = re.sub(r"^\d{3,7}\s*[-–]\s*", "", title).strip()
            url = match.group(2)
            external_id = match.group(3)

            body = block.split("* * *")[0]
            # لینک «ارسال پیشنهاد» جزو توضیحات نیست
            body = re.sub(r"^\s*\[ارسال پیشنهاد\]\([^)]*\)", "", body)

            # توضیحات: تا رسیدن به خط زمان/بودجه
            desc = body
            for pattern in (TIME_RE, BUDGET_RE, SKILL_RE):
                m = pattern.search(desc)
                if m:
                    desc = desc[:m.start()]
            description = clean_text(desc)
            if description.startswith("برای مشاهده اطلاعات پروژه"):
                description = ""

            budget = None
            m = BUDGET_RE.search(body)
            if m:
                budget = parse_budget(m.group(1))

            posted_at = None
            m = TIME_RE.search(body)
            if m:
                posted_at = parse_posted_at(m.group(1)) or clean_text(m.group(1))

            bids = None
            m = BIDS_RE.search(body)
            if m:
                bids = int(m.group(1))

            skills: list[str] = []
            for skill_match in SKILL_RE.finditer(body):
                skill = clean_text(skill_match.group(1))
                if skill and skill not in skills:
                    skills.append(skill)

            flags = [word for word in FLAG_WORDS if word in body]
            # پروژه‌های «پاداش» (هدیه به یک مجری خاص) قابل پیشنهاد دادن نیستند
            if "پاداش" in flags:
                continue

            records.append({
                "external_id": external_id,
                "title": title,
                "url": url,
                "description": description,
                "skills": skills,
                "budget_toman": budget,
                "client_deadline_days": None,
                "bids": bids,
                "posted_at": posted_at,
                "location": None,
                "flags": flags,
            })
        return merge_records(records)
