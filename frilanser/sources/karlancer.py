"""منبع کارلنسر (karlancer.com) — خواندن لیست پروژه‌ها (همه یا یک دسته‌بندی)."""

from __future__ import annotations

import re

from ..normalize import clean_text, parse_bids, parse_budget, parse_duration_days, parse_posted_at
from .base import BaseSource, after, before, merge_records, slice_blocks

CARD_RE = re.compile(
    r"\[\*{0,2}([^\]]{5,200}?)\*{0,2}\]\((https://www\.karlancer\.com/projects/([^)\s]+))\)[ \t]*([^\n]*)"
)

FLAG_WORDS = ("کیفیت حرفه‌ای", "فوری", "تمام وقت", "اسپانسر", "ویژه")
END_MARK = "مشاهده جزئیات پیشنهادهای این پروژه"
DESC_MARK = "ثبت پیشنهاد روی پروژه"
# خطوطی که مهارت نیستند و در انتهای کارت می‌آیند
NON_SKILL = ("مشاهده", "گزارش", "ثبت پیشنهاد", "کپی", "اشتراک", "جزئیات پروژه",
             "بودجه", "زمان پیشنهادی", "وضعیت")


class KarlancerSource(BaseSource):
    kind = "karlancer"
    label = "کارلنسر"

    def parse(self, text: str) -> list[dict]:
        blocks = slice_blocks(text, CARD_RE)
        records: list[dict] = []
        for match, block in blocks:
            title = clean_text(match.group(1))
            url = match.group(2)
            slug = match.group(3)
            external_id = slug.rsplit("-", 1)[-1] if "-" in slug else slug
            posted_at = parse_posted_at(match.group(4))

            body = before(block, END_MARK)
            desc_part = after(body, DESC_MARK, default=body)

            # مهارت‌ها خطوطِ کوتاهِ انتهای کارت هستند (بعد از برچسب‌های فوری/ویژه و ...)
            lines = [clean_text(x) for x in desc_part.splitlines()]
            skill_idx: list[int] = []
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                if not line:
                    continue
                if line in FLAG_WORDS or any(flag in line for flag in FLAG_WORDS):
                    break  # به برچسب‌های وضعیت رسیدیم؛ ادامه متعلق به توضیحات است
                if any(word in line for word in NON_SKILL):
                    break
                if len(line) > 45 or line.startswith("http") or line.startswith("!"):
                    break
                if re.match(r"^[\d\s]+$", line):
                    break
                skill_idx.append(i)
            skill_idx.reverse()
            skills = [lines[i] for i in skill_idx]

            cut = skill_idx[0] if skill_idx else len(lines)
            desc_lines = [
                line for line in lines[:cut]
                if line and line not in FLAG_WORDS and not any(w in line for w in NON_SKILL)
            ]
            description = clean_text(re.sub(r"\\([*#_\-\[\]])", r"\1", "\n".join(desc_lines)))

            budget = None
            m = re.search(r"بودجه\s*\n+\s*([^\n]*)", body)
            if m:
                budget = parse_budget(m.group(1))
            if budget is None:
                budget = parse_budget(before(body, "زمان پیشنهادی"))

            duration = None
            m = re.search(r"زمان پیشنهادی\s*\n+\s*([^\n]+)", body)
            if m:
                duration = parse_duration_days(m.group(1))

            location = None
            m = re.search(r"(?:امتیاز کارفرما\s*\n+\s*\([^)]*\)|کارفرمای جدید)\s*\n+\s*([^\n]+)", body)
            if m:
                location = clean_text(m.group(1))

            status = None
            m = re.search(r"وضعیت\s*\n+\s*([^\n]+)", body)
            if m:
                status = clean_text(m.group(1))

            flags: list[str] = []
            for flag in FLAG_WORDS:
                if flag in body:
                    flags.append(flag)
            if status:
                flags.append(status)

            records.append({
                "external_id": external_id,
                "title": title,
                "url": url,
                "description": description,
                "skills": skills,
                "budget_toman": budget,
                "client_deadline_days": duration,
                "bids": parse_bids(body),
                "posted_at": posted_at,
                "location": location,
                "flags": flags,
            })
        return merge_records(records)
