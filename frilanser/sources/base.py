"""پایه‌ی منابع داده: دریافت صفحه (شبکه یا فایل محلی) و تبدیل به متن."""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Iterable

from ..config import Config
from ..models import Project


class FetchError(RuntimeError):
    pass


class BaseSource:
    """هر منبع (پونیشا، کارلنسر، ...) از این کلاس مشتق می‌شود."""

    name = "base"
    kind = "base"
    label = "منبع"

    def __init__(self, cfg: Config, source_key: str):
        self.cfg = cfg
        self.key = source_key
        self.scfg = cfg.sources.get(source_key, {})
        self.cache_dir = cfg.cache_dir

    # ---------------- fetch ----------------
    def fetch_text(self, url: str, force: bool = False) -> str:
        """اگر url مسیر فایل محلی است آن را می‌خواند، در غیر این صورت از شبکه."""
        if not url.lower().startswith(("http://", "https://")):
            path = Path(url)
            if not path.is_absolute():
                path = self.cfg.root / url
            if not path.exists():
                raise FetchError(f"فایل اسنپ‌شات پیدا نشد: {path}")
            return path.read_text(encoding="utf-8")

        cache_file = self.cache_dir / f"{self.key}-{hashlib.md5(url.encode()).hexdigest()[:12]}.txt"
        if cache_file.exists() and not force:
            return cache_file.read_text(encoding="utf-8")

        if not self.cfg.allow_network:
            raise FetchError(
                f"دسترسی شبکه غیرفعال است (allow_network=false) و کش برای {url} وجود ندارد"
            )

        try:
            import requests  # noqa: PLC0415 - وابستگی اختیاری
        except ImportError as exc:  # pragma: no cover
            raise FetchError("برای دریافت زنده پکیج requests لازم است: pip install requests") from exc

        headers = {"User-Agent": self.cfg.fetch.get("user_agent", "frilanser/1.0")}
        resp = requests.get(url, headers=headers, timeout=self.cfg.fetch.get("timeout_seconds", 25))
        resp.raise_for_status()
        html = resp.text

        text = self.html_to_text(html)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(text, encoding="utf-8")
        time.sleep(float(self.cfg.fetch.get("delay_between_requests", 1.0)))
        return text

    @staticmethod
    def html_to_text(html: str) -> str:
        """HTML را به متن ساده تبدیل می‌کند (الگوی کارت‌ها در متن حفظ می‌شود)."""
        try:
            from bs4 import BeautifulSoup  # noqa: PLC0415
        except ImportError:
            text = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
            text = re.sub(r"(?s)<[^>]+>", "\n", text)
        else:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            text = soup.get_text("\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return text.strip()

    # ---------------- parse / collect ----------------
    def parse(self, text: str) -> list[dict]:
        raise NotImplementedError

    def to_projects(self, records: list[dict]) -> list[Project]:
        projects = []
        for rec in records:
            projects.append(
                Project.from_scrape(
                    source=self.key,
                    external_id=rec.get("external_id") or rec.get("url"),
                    title=rec.get("title", "").strip(),
                    url=rec.get("url", ""),
                    description=rec.get("description", ""),
                    skills=rec.get("skills", []) or [],
                    budget_toman=rec.get("budget_toman"),
                    client_deadline_days=rec.get("client_deadline_days"),
                    posted_at=rec.get("posted_at"),
                    bids=rec.get("bids"),
                    location=rec.get("location"),
                    flags=rec.get("flags", []) or [],
                )
            )
        return projects

    def list_urls(self) -> list[str]:
        return [self.scfg["listing_url"]] if self.scfg.get("listing_url") else []

    def collect(self, extra_urls: Iterable[str] | None = None, force: bool = False) -> list[Project]:
        urls = list(extra_urls or []) or self.list_urls()
        records: list[dict] = []
        for url in urls:
            try:
                text = self.fetch_text(url, force=force)
            except FetchError as exc:
                print(f"  ! خطا در دریافت {url}: {exc}")
                continue
            parsed = self.parse(text)
            records.extend(parsed)
            print(f"  · {self.label}: {len(parsed)} آگهی از {url if len(url) < 70 else url[:70] + '…'}")
        return self.to_projects(records)


def merge_records(records: list[dict]) -> list[dict]:
    """کارت‌های تکراری یک پروژه را ادغام می‌کند (هر سایت دو بار رندر می‌کند)."""
    merged: dict[str, dict] = {}
    for rec in records:
        key = str(rec.get("external_id"))
        if not key:
            continue
        cur = merged.get(key)
        if not cur:
            merged[key] = dict(rec)
            continue
        if len(rec.get("description", "")) > len(cur.get("description", "")):
            cur["description"] = rec["description"]
        cur["skills"] = list(dict.fromkeys((cur.get("skills") or []) + (rec.get("skills") or [])))
        cur["flags"] = list(dict.fromkeys((cur.get("flags") or []) + (rec.get("flags") or [])))
        for field_name in ("budget_toman", "client_deadline_days", "bids", "posted_at", "location", "title"):
            if cur.get(field_name) in (None, "", 0) and rec.get(field_name) not in (None, "", 0):
                cur[field_name] = rec[field_name]
        if (cur.get("budget_toman") or 0) < (rec.get("budget_toman") or 0):
            cur["budget_toman"] = rec.get("budget_toman")
    return list(merged.values())


def slice_blocks(text: str, pattern: re.Pattern) -> list[tuple[re.Match, str]]:
    """متن را بر اساس لینک پروژه‌ها به بلوک‌های مجزا می‌بُرد."""
    matches = list(pattern.finditer(text))
    blocks: list[tuple[re.Match, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((m, text[m.end():end]))
    return blocks


def after(text: str, marker: str, default: str = "") -> str:
    idx = text.find(marker)
    return text[idx + len(marker):] if idx >= 0 else default


def before(text: str, *markers: str) -> str:
    cut = len(text)
    for marker in markers:
        idx = text.find(marker)
        if idx >= 0:
            cut = min(cut, idx)
    return text[:cut]


def first_match(patterns: list[str], text: str, flags=0) -> re.Match | None:
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            return m
    return None
