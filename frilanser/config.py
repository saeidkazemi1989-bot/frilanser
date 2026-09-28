"""بارگذاری تنظیمات از config.toml.

در حالت عادی ریشه‌ی پروژه همان پوشه‌ی ریپو است. در حالت اجرایی (PyInstaller/EXE)
منابع فقط-خواندنی داخل باندل هستند و داده‌ها/خروجی‌ها در یک پوشه‌ی قابل‌نوشتن
(کنار فایل اجرایی یا LOCALAPPDATA) نوشته می‌شوند.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_PACKAGE_PARENT = Path(__file__).resolve().parent.parent  # پوشه‌ی ریپو در حالت عادی


def _detect_dirs() -> tuple[Path, Path]:
    """(پوشه‌ی کاربر/قابل‌نوشتن، پوشه‌ی منابع باندل)"""
    # ریشه‌ی اجباری (اندروید / سفارشی): FRILANSER_HOME
    forced = os.environ.get("FRILANSER_HOME")
    if forced:
        try:
            cand = Path(forced)
            cand.mkdir(parents=True, exist_ok=True)
            if os.access(cand, os.W_OK):
                return cand, _PACKAGE_PARENT
        except OSError:
            pass
    if not getattr(sys, "frozen", False):
        return _PACKAGE_PARENT, _PACKAGE_PARENT

    bundle = Path(getattr(sys, "_MEIPASS", _PACKAGE_PARENT))
    exe_dir = Path(sys.executable).resolve().parent
    candidates: list[Path] = [Path.cwd(), exe_dir]

    # اگر در یکی از این پوشه‌ها config.toml هست، همان را به‌عنوان پوشه‌ی پروژه می‌گیریم
    for cand in candidates:
        try:
            if (cand / "config.toml").exists() and os.access(cand, os.W_OK):
                return cand, bundle
        except OSError:
            continue
    for cand in candidates:
        try:
            if os.access(cand, os.W_OK):
                return cand, bundle
        except OSError:
            continue

    fallback = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "frilanser"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback, bundle


ROOT_DIR, BUNDLE_DIR = _detect_dirs()
ROOT = ROOT_DIR          # سازگاری با کدهای قبلی
BUNDLE = BUNDLE_DIR
DEFAULT_CONFIG_PATH = ROOT / "config.toml"


def load_config(path: str | os.PathLike | None = None) -> "Config":
    cfg_path = Path(path) if path else (
        DEFAULT_CONFIG_PATH if DEFAULT_CONFIG_PATH.exists() else BUNDLE / "config.toml"
    )
    with open(cfg_path, "rb") as fh:
        raw = tomllib.load(fh)
    return Config(raw, cfg_path)


def bootstrap_user_files(cfg: "Config") -> list[str]:
    """در حالت اجرایی، فایل‌های پیش‌فرض را کنار برنامه کپی می‌کند (قابل ویرایش توسط کاربر)."""
    if BUNDLE == ROOT:
        return []
    copied: list[str] = []

    user_cfg = ROOT / "config.toml"
    if not user_cfg.exists() and (BUNDLE / "config.toml").exists():
        shutil.copy2(BUNDLE / "config.toml", user_cfg)
        copied.append(str(user_cfg))

    user_raw = ROOT / "data" / "raw"
    bundle_raw = BUNDLE / "data" / "raw"
    user_raw.mkdir(parents=True, exist_ok=True)
    if bundle_raw.exists() and not any(user_raw.iterdir()):
        for item in bundle_raw.iterdir():
            if item.is_file():
                shutil.copy2(item, user_raw / item.name)
        copied.append(str(user_raw))
    return copied


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

    @property
    def bundle(self) -> Path:
        return BUNDLE

    def subpath(self, *parts: str) -> Path:
        p = ROOT.joinpath(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def data_dir(self) -> Path:
        return self.subpath(_dig(self.raw, "app", "data_dir", default="data"))

    def _under_data(self, key: str, name: str) -> Path:
        """مسیرهای داخل پوشه‌ی داده‌ها؛ اگر data_dir مطلق باشد، آن‌ها هم مطلق می‌شوند."""
        override = _dig(self.raw, "app", key)
        if override:
            cand = Path(override)
            if cand.is_absolute():
                return self.subpath(str(cand))
            # مسیر نسبی (مثل data/raw) → نسبت به پوشه‌ی داده‌ها
            return self.subpath(str(self.data_dir), cand.name)
        return self.subpath(str(self.data_dir), name)

    @property
    def raw_dir(self) -> Path:
        return self._under_data("raw_dir", "raw")

    @property
    def cache_dir(self) -> Path:
        return self._under_data("cache_dir", "cache")

    @property
    def outbox_dir(self) -> Path:
        return self.subpath(_dig(self.raw, "app", "outbox_dir", default="outbox"))

    @property
    def demo_dir(self) -> Path:
        return self.subpath(_dig(self.raw, "app", "demo_dir", default="outbox/demos"))

    @property
    def react_dir(self) -> Path:
        return self.subpath(_dig(self.raw, "app", "react_dir", default="outbox/react"))

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
