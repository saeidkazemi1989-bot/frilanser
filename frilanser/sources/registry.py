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


def build_sources(cfg: Config) -> dict[str, BaseSource]:
    sources: dict[str, BaseSource] = {}
    for key, scfg in cfg.sources.items():
        if not scfg.get("enabled", True):
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
