"""نسخه‌ی برنامه و تشخیص سکو (ویندوز / اندروید / لینوکس)."""

from __future__ import annotations

import os
import sys

# نسخه‌ی برنامه — هر تغییر مهم این عدد را بالا ببرید.
# قالب: major.minor.patch
__version__ = "1.0.0"

# کانال پیش‌فرض انتشار (شاخه‌ای که مانیفست به‌روزرسانی روی آن است)
DEFAULT_BRANCH = "arena/01a0e651-frilanser"

REPO_OWNER = "saeidkazemi1989-bot"
REPO_NAME = "frilanser"


def is_android() -> bool:
    """آیا داخل یک بسته‌ی اندرویدی (python-for-android) اجرا می‌شویم؟"""
    return (
        "ANDROID_ARGUMENT" in os.environ
        or "ANDROID_APP_PATH" in os.environ
        or "android" in sys.platform
        or os.environ.get("FRILANSER_PLATFORM") == "android"
    )


def platform_key() -> str:
    """`android` | `windows` | `linux`"""
    if is_android():
        return "android"
    if os.name == "nt" or sys.platform.startswith("win"):
        return "windows"
    return "linux"


def version_tuple(text: str) -> tuple:
    """تبدیل رشته‌ی نسخه به تاپل عددی برای مقایسه."""
    parts = []
    for chunk in str(text or "0").strip().split(".")[:3]:
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(candidate: str, current: str) -> bool:
    """آیا نسخه‌ی کاندید واقعاً جدیدتر است؟"""
    return version_tuple(candidate) > version_tuple(current)
