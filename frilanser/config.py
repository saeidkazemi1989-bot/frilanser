"""بارگذاری تنظیمات از config.toml."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.toml"


def load_config(path: str | os.PathLike | None = None) -> "Config":
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(cfg_path, "rb") as fh:
        raw = tomllib.load(fh)
    return Config(raw, cfg_path)


def _dig(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


@dataclass
class Config:
    raw: dict = field(default_factory=dict)
    path: Path = DEFAULT_CONFIG_PATH

    # ---------- paths ----------
    @property
    def root(self) -> Path:
        return ROOT

    def subpath(self, *parts: str) -> Path:
        p = ROOT.joinpath(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def data_dir(self) -> Path:
        return self.subpath(_dig(self.raw, "app", "data_dir", default="data"))

    @property
    def raw_dir(self) -> Path:
        return self.subpath(_dig(self.raw, "app", "raw_dir", default="data/raw"))

    @property
    def cache_dir(self) -> Path:
        return self.subpath(_dig(self.raw, "app", "cache_dir", default="data/cache"))

    @property
    def outbox_dir(self) -> Path:
        return self.subpath(_dig(self.raw, "app", "outbox_dir", default="outbox"))

    @property
    def demo_dir(self) -> Path:
        return self.subpath(_dig(self.raw, "app", "demo_dir", default="outbox/demos"))

    @property
    def report_dir(self) -> Path:
        return self.subpath(_dig(self.raw, "app", "report_dir", default="outbox/reports"))

    # ---------- pricing ----------
    @property
    def pricing(self) -> dict:
        return self.raw.get("pricing", {})

    @property
    def hourly_rate(self) -> int:
        return int(self.pricing.get("hourly_rate_toman", 450000))

    @property
    def min_price(self) -> int:
        return int(self.pricing.get("min_project_price_toman", 5_000_000))

    @property
    def round_to(self) -> int:
        return int(self.pricing.get("round_to_toman", 500_000))

    @property
    def commission(self) -> float:
        return float(self.pricing.get("platform_commission", 0.10))

    @property
    def risk_buffer(self) -> float:
        return float(self.pricing.get("risk_buffer", 0.15))

    @property
    def max_hours(self) -> float:
        return float(self.pricing.get("max_hours", 24))

    @property
    def work_hours_per_day(self) -> float:
        return float(self.pricing.get("work_hours_per_day", 6))

    def complexity(self, category: str) -> float:
        table = self.pricing.get("complexity_multiplier", {}) or {}
        return float(table.get(category, table.get("other", 1.0)))

    # ---------- screening ----------
    @property
    def screening(self) -> dict:
        return self.raw.get("screening", {})

    def sval(self, key: str, default):
        return self.screening.get(key, default)

    # ---------- sources ----------
    @property
    def sources(self) -> dict:
        return self.raw.get("sources", {})

    def enabled_sources(self) -> list[str]:
        return [name for name, cfg in self.sources.items() if cfg.get("enabled", True)]

    # ---------- fetch ----------
    @property
    def fetch(self) -> dict:
        return self.raw.get("fetch", {})

    @property
    def allow_network(self) -> bool:
        return bool(self.fetch.get("allow_network", True))

    @property
    def app(self) -> dict:
        return self.raw.get("app", {})
