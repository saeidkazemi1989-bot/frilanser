"""ساخت و مدیریت منابع داده (سایت‌های فریلنسری)."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import Config
from ..models import Project
from .base import BaseSource
from .karlancer import KarlancerSource
from .parscoders import ParsCodersSource
from .ponisha import PonishaSource

SOURCE_CLASSES: dict[str, type[BaseSource]] = {
    "ponisha": PonishaSource,
    "karlancer": KarlancerSource,
    "parscoders": ParsCodersSource,
}

# فایلِ انتخابِ کاربر (کدام سایت‌ها اسکن شوند) — کنار خروجی‌ها نوشته می‌شود
PREFS_FILE = "source-prefs.json"


SECRETS_FILE = "source-secrets.json"


def load_source_secrets(cfg: Config) -> dict[str, str]:
    """کوکی/نشانه‌ی ورودِ هر سایت (جدا از تنظیمات، در فایلِ خروجی‌ها)."""
    path = Path(cfg.outbox_dir) / SECRETS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    cookies = data.get("cookie") if isinstance(data, dict) else None
    return {str(k): str(v or "").strip() for k, v in (cookies or {}).items()} \
        if isinstance(cookies, dict) else {}


def save_source_secrets(cfg: Config, cookies: dict[str, str]) -> dict[str, str]:
    """ذخیره‌ی کوکیِ ورود (برای سایت‌هایی که فقط با اکانت آگهی نشان می‌دهند)."""
    known = set(cfg.sources)
    clean = {k: str(v or "").strip() for k, v in (cookies or {}).items() if k in known}
    clean = {k: v for k, v in clean.items() if v}          # خالی‌ها حذف شوند
    path = Path(cfg.outbox_dir) / SECRETS_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"cookie": clean}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    except OSError:
        pass
    return clean


def load_source_prefs(cfg: Config) -> dict[str, bool]:
    """انتخابِ کاربر: کدام سایت‌ها اسکن شوند؟

    در یک فایلِ جداگانه (کنار خروجی‌ها) ذخیره می‌شود تا تنظیماتِ اصلی دست‌نخورده
    بماند و در به‌روزرسانی برنامه هم از بین نرود.
    """
    path = Path(cfg.outbox_dir) / PREFS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    prefs = data.get("enabled") if isinstance(data, dict) else None
    return {str(k): bool(v) for k, v in (prefs or {}).items()} if isinstance(prefs, dict) else {}


def save_source_prefs(cfg: Config, enabled: dict[str, bool]) -> dict[str, bool]:
    """ذخیره‌ی انتخابِ کاربر؛ فقط کلیدهایی که در config.toml هستند نگه داشته می‌شوند."""
    known = set(cfg.sources)
    clean = {k: bool(v) for k, v in (enabled or {}).items() if k in known}
    path = Path(cfg.outbox_dir) / PREFS_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"enabled": clean}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    except OSError:
        pass
    return clean


def source_states(cfg: Config) -> dict[str, bool]:
    """وضعیتِ فعلیِ هر سایت (پیش‌فرض از config.toml + انتخابِ کاربر)."""
    prefs = load_source_prefs(cfg)
    return {key: bool(prefs.get(key, scfg.get("enabled", True)))
            for key, scfg in cfg.sources.items()}


def build_sources(cfg: Config) -> dict[str, BaseSource]:
    """ساخت منابعِ فعال: طبق config.toml **و** انتخابی که کاربر در برنامه کرده است."""
    states = source_states(cfg)
    sources: dict[str, BaseSource] = {}
    for key, scfg in cfg.sources.items():
        if not states.get(key, True):
            continue
        cls = SOURCE_CLASSES.get(scfg.get("kind", key))
        if not cls:
            continue
        sources[key] = cls(cfg, key)
    return sources


def snapshot_files(cfg: Config, key: str) -> list[Path]:
    """فایل‌های اسنپ‌شاتِ ذخیره‌شده برای یک منبع (json یا md/html).

    نام فایل باید با کلید منبع شروع شود؛ اگر کلیدِ طولانی‌تری هم همان فایل را
    بخواهد (مثلاً karlancer در برابر karlancer_programming)، فایل به کلید
    طولانی‌تر تعلق می‌گیرد تا آگهی‌ها تکراری نشوند.
    """
    stem_keys = list(cfg.sources.keys())
    found: list[Path] = []
    for path in sorted(cfg.raw_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".json", ".md", ".html"):
            continue
        stem = path.stem
        if not (stem == key or stem.startswith(key + "-") or stem.startswith(key + "_")):
            continue
        longer_owner = any(
            k != key and len(k) > len(key)
            and (stem == k or stem.startswith(k + "-") or stem.startswith(k + "_"))
            for k in stem_keys
        )
        if longer_owner:
            continue
        found.append(path)
    return found


def load_snapshot_records(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            records = data.get("projects") or data.get("records") or []
        else:
            records = data
        return [r for r in records if isinstance(r, dict)]
    return []  # فایل‌های متنی با parser مخصوص سایت پردازش می‌شوند


def collect_snapshots(cfg: Config, sources: dict[str, BaseSource]) -> list[Project]:
    """خواندن آگهی‌ها از اسنپ‌شات‌های ذخیره‌شده (بدون نیاز به اینترنت)."""
    projects: list[Project] = []
    for key, source in sources.items():
        files = snapshot_files(cfg, key)
        for path in files:
            if path.suffix.lower() == ".json":
                records = load_snapshot_records(path)
                source_label = f"{source.label} (اسنپ‌شات {path.name})"
            else:
                text = path.read_text(encoding="utf-8")
                records = source.parse(text)
                source_label = f"{source.label} (اسنپ‌شات {path.name})"
            if records:
                projects.extend(source.to_projects(records))
                print(f"  · {source_label}: {len(records)} آگهی")
    return projects
