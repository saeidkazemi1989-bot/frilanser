"""پایه‌ی منابع داده: دریافت صفحه (شبکه یا فایل محلی) و تبدیل به متن."""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

from ..config import Config
from ..models import Project


# عناصرِ بلوکی: فقط این‌ها در تبدیل به متن خطِ جدید می‌گیرند.
_BLOCK_TAGS = [
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table",
    "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
]

# پیوندی که به صفحه‌ی یک پروژه می‌رود (برای استخراجِ عمومی)
_GENERIC_LINK_RE = re.compile(
    r"\[([^\]]{5,200})\]\((https?://[^\s)]+?/(?:projects?|jobs?|gigs?)/[^)\s]+)\)"
)

# صفاتی که نشانه‌ی «این یک پروژه نیست» است (لینک‌های ناوبری و …)
_GENERIC_STOP = (
    "new", "search", "all", "index", "list", "create", "login", "register",
    "category", "categories", "skills", "skill", "page", "filter",
)


class FetchError(RuntimeError):
    """خطا در دریافتِ یک صفحه؛ نشانی و کدِ پاسخ را هم همراه دارد (برای گزارش)."""

    def __init__(self, message: str, url: str = "", status: int | None = None):
        super().__init__(message)
        self.url = url
        self.status = status


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
        # گزارشِ آخرین دریافت‌ها (برای اینکه بدانیم چرا آگهی جدید نمی‌آید)
        self.fetch_log: list[dict] = []
        # آخرین HTML خام (برای استخراجِ عمومی و گزارشِ ساختار)
        self.last_html: str = ""
        # نمونه پیوندهای پروژه که در صفحه پیدا شد
        self.link_samples: list[str] = []
        # آیا صفحه به‌نظر می‌رسد فهرست را با جاوااسکریپت می‌سازد؟
        self.empty_like_js = False
        # اگر دریافتِ زنده شکست خورد و از کشِ کهنه استفاده شد، این پرچم روشن
        # می‌شود تا اسکن «موفقِ قلابی» به نظر نرسد.
        self.used_stale_cache = False

    def _cookie(self) -> str:
        """کوکیِ ورود به سایت (اگر کاربر در برنامه یا config گذاشته باشد)."""
        value = str(self.scfg.get("cookie") or "").strip()
        if value:
            return value
        try:
            from .registry import load_source_secrets

            return str(load_source_secrets(self.cfg).get(self.key) or "").strip()
        except Exception:  # noqa: BLE001
            return ""

    # ---------------- fetch ----------------
    def fetch_text(self, url: str, force: bool = False) -> str:
        """اگر url مسیر فایل محلی است آن را می‌خواند، در غیر این صورت از شبکه."""
        entry: dict = {"url": url, "ok": False, "status": None, "chars": 0,
                       "error": "", "cached": False, "sample": ""}
        self.fetch_log.append(entry)
        if len(self.fetch_log) > 40:
            self.fetch_log[:] = self.fetch_log[-40:]

        if not url.lower().startswith(("http://", "https://")):
            path = Path(url)
            if not path.is_absolute():
                path = self.cfg.root / url
            if not path.exists():
                entry["error"] = f"فایل اسنپ‌شات پیدا نشد: {path}"
                raise FetchError(entry["error"], url=url)
            text = path.read_text(encoding="utf-8")
            entry.update({"ok": True, "chars": len(text), "cached": True,
                          "sample": text[:400]})
            return text

        cache_file = self.cache_dir / f"{self.key}-{hashlib.md5(url.encode()).hexdigest()[:12]}.txt"
        if cache_file.exists() and not force and self._cache_is_fresh(cache_file):
            text = cache_file.read_text(encoding="utf-8")
            entry.update({"ok": True, "chars": len(text), "cached": True,
                          "sample": text[:400]})
            return text

        if not self.cfg.allow_network:
            entry["error"] = (f"دسترسی شبکه غیرفعال است (allow_network=false) و "
                              f"کشِ تازه‌ای برای {url} وجود ندارد")
            raise FetchError(entry["error"], url=url)

        # زنجیره‌ی دریافت در frilanser/http.py است: requests → کتابخانه‌ی
        # استاندارد → بدون تأییدِ گواهی → واسطه‌های عمومی. اینجا فقط نتیجه را
        # می‌خوانیم تا هیچ مسیری امتحان‌نشده نماند (قبلاً اگر requests سالم بود،
        # مسیرِ پشتیبان اصلاً امتحان نمی‌شد و دریافت همان‌جا رها می‌شد).
        from .. import http

        headers = {"User-Agent": self.cfg.fetch.get("user_agent", "frilanser/1.0"),
                   "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.6"}
        cookie = self._cookie()
        if cookie:
            headers["Cookie"] = cookie

        use_relays = bool(self.cfg.fetch.get("use_relays", True))
        relays = self.cfg.fetch.get("relays") or None
        if relays:
            relays = tuple((str(name), str(tmpl)) for name, tmpl in relays)
        got = http.get_text(url, timeout=self.cfg.fetch.get("timeout_seconds", 25),
                            headers=headers, allow_relay=use_relays,
                            relays=relays or http.RELAYS)
        entry["status"] = got.get("status")
        entry["how"] = got.get("how") or ""

        if not (got.get("ok") and (got.get("text") or "").strip()):
            entry["error"] = f"{got.get('error') or 'خطای ناشناخته'} ({entry['how']})"
            if got.get("relay_errors"):
                entry["relays"] = got["relay_errors"]
            # آخرین چاره: کشِ کهنه — فقط اگر واقعاً محتوای آگهی داشته باشد
            # (کش‌های چندکاراکتری ارزشِ نشان دادن ندارند و اسکن را قلابی موفق
            # نشان می‌دادند).
            min_chars = int(self.cfg.fetch.get("min_stale_chars", 400) or 0)
            if cache_file.exists():
                try:
                    old = cache_file.read_text(encoding="utf-8")
                except OSError:
                    old = ""
                if len(old.strip()) >= min_chars:
                    self.used_stale_cache = True
                    entry.update({"ok": True, "stale": True, "chars": len(old),
                                  "cached": "کهنه", "sample": old[:400]})
                    return old
                if old.strip():
                    entry["error"] += f" | کشِ موجود فقط {len(old.strip())} کاراکتر است (نادیده گرفته شد)"
            raise FetchError(entry["error"], url=url, status=got.get("status"))

        html = got["text"]
        entry.update({"ok": True, "chars": len(html)})
        self.last_html = html
        text = self.html_to_text(html, base_url=url)
        entry["sample"] = text[:400]
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(text, encoding="utf-8")
        time.sleep(float(self.cfg.fetch.get("delay_between_requests", 1.0)))
        return text

    def fetch_report(self) -> dict:
        """خلاصه‌ی آخرین تلاش‌ها برای دریافت (برای نمایش در «گزارشِ اسکن»)."""
        ok = [e for e in self.fetch_log if e.get("ok")]
        return {
            "key": self.key,
            "label": getattr(self, "label", self.key),
            "has_cookie": bool(self._cookie()),
            "attempts": len(self.fetch_log),
            "ok": len(ok),
            "failed": len(self.fetch_log) - len(ok),
            "chars": sum(int(e.get("chars") or 0) for e in self.fetch_log),
            "log": self.fetch_log[-12:],
        }

    def _cache_is_fresh(self, cache_file: Path) -> bool:
        """آیا کش هنوز اعتبار دارد؟

        پیش‌تر کش همیشه معتبر بود، برای همین بعد از اولین دریافت، اسکن‌های بعدی
        همان صفحه‌ی قدیمی را می‌خواندند و آگهی‌های جدید هرگز نمی‌آمدند. حالا با
        ``[fetch] cache_ttl_hours`` (پیش‌فرض ۲ ساعت) کنترل می‌شود و دکمه‌ی
        «اسکنِ الان» همیشه تازه می‌گیرد (force=True).
        """
        ttl_hours = float(self.cfg.fetch.get("cache_ttl_hours", 2) or 0)
        if ttl_hours <= 0:
            return False
        try:
            age_hours = (time.time() - cache_file.stat().st_mtime) / 3600.0
        except OSError:
            return False
        return age_hours < ttl_hours

    @staticmethod
    def html_to_text(html: str, base_url: str = "") -> str:
        """HTML را به متنِ مارک‌داون‌مانند تبدیل می‌کند.

        **نکته‌ی حیاتی:** پیوندها باید به شکلِ مارک‌داون (``[عنوان](نشانی)``)
        در متن بمانند، چون همه‌ی تحلیل‌گرها آگهی را از روی پیوندِ صفحه‌ی پروژه
        پیدا می‌کنند. نسخه‌ی قبلی با ``get_text`` پیوندها را می‌بُرید و برای
        همین با وجود دریافتِ موفقِ صفحه، صفر آگهی استخراج می‌شد.
        تیترها هم با ``#`` مشخص می‌شوند (تحلیل‌گرِ پارس‌کدرز به ``######``
        نیاز دارد).
        """
        try:
            # بسته‌ی اندروید typing_extensions را همراه ندارد و بدون آن
            # ایمپورتِ bs4 شکست می‌خورد؛ قبل از ایمپورت آن را تأمین می‌کنیم.
            from frilanser.compat import ensure_typing_extensions

            ensure_typing_extensions()
            from bs4 import BeautifulSoup  # noqa: PLC0415
        except ImportError:
            import html as _html_mod

            text = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)

            def _link(match: re.Match) -> str:
                label = re.sub(r"(?s)<[^>]+>", "", match.group(2)).strip()
                return f"[{label}]({match.group(1)})" if label else ""

            text = re.sub(r'(?is)<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', _link, text)
            text = re.sub(r"(?is)<h([1-6])[^>]*>", lambda m: "\n" + "#" * int(m.group(1)) + " ", text)
            text = re.sub(r"(?s)<[^>]+>", "\n", text)
            text = _html_mod.unescape(text)
        else:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg", "template"]):
                tag.decompose()

            # ۱) پیوندها → مارک‌داون (نسبی‌ها با نشانیِ پایه مطلق می‌شوند)
            for anchor in soup.find_all("a"):
                href = str(anchor.get("href") or "").strip()
                if not href or href.startswith("#") \
                        or href.lower().startswith(("javascript:", "mailto:", "tel:")):
                    continue
                if base_url and not href.lower().startswith(("http://", "https://")):
                    href = urljoin(base_url, href)
                label = anchor.get_text(" ").strip()
                if not label:
                    continue
                anchor.replace_with(f"[{label}]({href})")

            # ۲) تیترها → # / ## / … / ######
            for level in range(1, 7):
                for heading in soup.find_all(f"h{level}"):
                    heading.insert(0, "#" * level + " ")

            # ۳) جداکننده‌ی افقی
            for rule in soup.find_all("hr"):
                rule.replace_with("\n* * *\n")

            # ۴) فقط عناصرِ بلوکی خطِ جدید می‌گیرند تا محتوایِ درون‌خطی
            #    (مثل عنوان و زمانِ انتشار) در یک خط بماند
            for tag in soup.find_all(_BLOCK_TAGS):
                tag.insert_before("\n")
                tag.insert_after("\n")

            text = soup.get_text("")

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
        """نشانیِ فهرستِ این منبع (از تنظیمات، وگرنه از پیش‌فرضِ داخل برنامه)."""
        from .defaults import listing_url_for

        url = listing_url_for(self.key, self.scfg)
        urls = [url] if url else []
        for extra in (self.scfg.get("alt_listing_urls") or []):
            extra = str(extra or "").strip()
            if extra and extra not in urls:
                urls.append(extra)
        return urls

    def generic_records(self, text: str) -> list[dict]:
        """استخراجِ عمومیِ آگهی‌ها از روی پیوندهایِ صفحه.

        هر پیوندی که به صفحه‌ی یک پروژه برود (مثل ``/project/123`` یا
        ``/projects/slug``) یک آگهی است؛ عنوان همان متنِ پیوند و توضیح و
        بودجه از متنِ بعد از آن برداشته می‌شود. این متد وقتی به کار می‌آید که
        قالبِ سایت عوض شده و تحلیل‌گرِ اختصاصی دیگر چیزی پیدا نکند.
        """
        records: list[dict] = []
        seen: set[str] = set()
        matches = list(_GENERIC_LINK_RE.finditer(text))
        for index, match in enumerate(matches):
            title = match.group(1).strip().strip("*").strip()
            url = match.group(2).strip()
            tail = url.rstrip("/").split("/")[-1]
            if not tail or tail.lower() in _GENERIC_STOP:
                continue
            key = url.split("?")[0]
            if key in seen:
                continue
            seen.add(key)

            end = matches[index + 1].start() if index + 1 < len(matches) \
                else min(len(text), match.end() + 1500)
            block = text[match.end():end]

            from ..normalize import (  # import محلی: وابستگیِ دور
                clean_text, parse_bids, parse_budget, parse_deadline_days,
            )

            description = clean_text(block)[:1200]
            record = {
                "external_id": tail,
                "title": clean_text(title)[:200],
                "url": url,
                "description": description,
                "budget_toman": parse_budget(block),
                "bids": parse_bids(block),
                "client_deadline_days": parse_deadline_days(block),
                "skills": [],
                "flags": [],
            }
            if record["title"]:
                records.append(record)
        return records

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
            how = "تحلیل‌گرِ اختصاصی"
            if not parsed:
                # قالبِ سایت عوض شده؟ استخراجِ عمومی را امتحان می‌کنیم.
                parsed = self.generic_records(text)
                how = "استخراجِ عمومی" if parsed else "هیچ‌کدام"
            if parsed:
                self.link_samples = [str(r.get("url") or "") for r in parsed[:5]]
            else:
                # نمونه پیوندهای پروژه در صفحه (برای گزارشِ ساختار)
                self.link_samples = [
                    m.group(2) for m in _GENERIC_LINK_RE.finditer(text)][:5]
                # صفحه‌هایی که فهرست را با جاوااسکریپت می‌سازند، در متنِ خام
                # چیزی ندارند؛ این را در گزارش می‌گوییم.
                self.empty_like_js = bool(
                    re.search(r"no results? found|نتیجه‌ای یافت نشد", text, re.I))
            records.extend(parsed)
            print(f"  · {self.label}: {len(parsed)} آگهی از "
                  f"{url if len(url) < 70 else url[:70] + '…'} ({how})")
            if records:
                # نشانی‌های جایگزین فقط وقتی امتحان می‌شوند که چیزی پیدا نشده باشد
                break
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
