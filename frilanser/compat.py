"""سازگاری با بسته‌هایی که وابستگی‌های فرعی را کامل همراه ندارند.

تجربه‌ی واقعی: بسته‌ی اندروید (ساخته‌ی buildozer/python-for-android) کتابخانه‌ی
``requests`` را داشت اما ``urllib3``/``certifi`` را نه، و ``beautifulsoup4`` را
داشت اما ``typing_extensions`` را نه. نتیجه این بود که هم ``import requests``
و هم ``import bs4`` روی خود گوشی با ``ModuleNotFoundError`` شکست می‌خوردند و
برنامه هیچ آگهی‌ای نشان نمی‌داد.

این ماژول دو کار می‌کند:

۱. با استفاده از «کتابخانه‌ی استاندارد» جانشینِ بسیار کوچکی برای
   ``typing_extensions`` می‌سازد تا ``bs4`` بتواند ایمپورت شود (در پایتون ۳.۱۱
   همه‌ی نام‌های مورد نیاز در خود ``typing`` هستند).
۲. گزارشی از وضعیتِ واقعیِ ایمپورتِ کتابخانه‌ها می‌دهد تا صفحه‌ی
   «گزارشِ اسکن»/«خودآزمایی» بتواند دقیقاً بگوید کدام کتابخانه روی دستگاه
   کار می‌کند و کدام نه.

هیچ خطری ندارد: اگر نسخه‌ی واقعیِ ``typing_extensions`` موجود باشد، کاری
نمی‌کند و فقط از آن استفاده می‌شود.
"""

from __future__ import annotations

import sys
import types

# نام‌هایی که beautifulsoup4 از typing_extensions می‌خواهد.
_TYPING_EXTENSIONS_NAMES = (
    "runtime_checkable",
    "Protocol",
    "TypeAlias",
    "Literal",
    "Self",
)


def _make_typing_extensions_stub() -> types.ModuleType | None:
    """یک ماژولِ جانشین و بسیار کوچک برای typing_extensions می‌سازد."""
    import typing

    module = types.ModuleType("typing_extensions")
    module.__doc__ = "جانشینِ کم‌حجمِ typing_extensions (ساخته‌ی فریلنس‌یار)"
    # نشانه‌ای تا گزارش‌ها بتوانند بگویند این نسخه‌ی واقعی نیست.
    module.__frilanser_stub__ = True  # type: ignore[attr-defined]
    found = False
    for name in _TYPING_EXTENSIONS_NAMES:
        value = getattr(typing, name, None)
        if value is None:
            continue
        setattr(module, name, value)
        found = True
    if not found:
        return None
    # برخی کتابخانه‌ها این پرچم را چک می‌کنند.
    module.TYPE_CHECKING = False  # type: ignore[attr-defined]
    return module


def ensure_typing_extensions() -> bool:
    """مطمئن می‌شود ``import typing_extensions`` کار می‌کند.

    اگر نسخه‌ی واقعی نصب و سالم باشد همان استفاده می‌شود؛ در غیر این صورت
    جانشینِ ساخته‌شده از ``typing`` جای آن را می‌گیرد (حتی اگر مدخلِ قبلی در
    ``sys.modules`` خراب یا نیمه‌کاره باشد). خروجی نشان می‌دهد که ایمپورت در
    نهایت ممکن است یا نه.
    """
    saved = sys.modules.get("typing_extensions")
    try:
        # اول نسخه‌ی واقعی را امتحان می‌کنیم (چه از قبل ایمپورت شده باشد چه نه).
        import typing_extensions as _real

        if getattr(_real, "Protocol", None) is not None and not getattr(
            _real, "__frilanser_stub__", False
        ):
            return True
    except Exception:  # noqa: BLE001 - نسخه‌ی موجود خراب یا ناقص است
        pass

    stub = _make_typing_extensions_stub()
    if stub is None:
        return False
    sys.modules["typing_extensions"] = stub
    try:
        import typing_extensions  # noqa: F401

        return True
    except ImportError:  # pragma: no cover - فقط اگر جانشین هم خراب باشد
        if saved is not None:
            sys.modules["typing_extensions"] = saved
        else:
            sys.modules.pop("typing_extensions", None)
        return False


def ensure_bs4() -> bool:
    """``import bs4`` را آماده می‌کند و می‌گوید موفق بود یا نه.

    هشدارِ «soupsieve نصب نیست» را خاموش می‌کنیم چون برنامه هرگز از انتخاب‌گرهای
    CSS استفاده نمی‌کند و این هشدار فقط لاگِ گوشی را شلوغ می‌کرد.
    """
    ensure_typing_extensions()
    import warnings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import bs4  # noqa: F401

        return True
    except ImportError:
        return False


def probe(module_name: str) -> bool | str:
    """وضعیت ایمپورت یک کتابخانه: ``True`` یا متنِ خطا."""
    if module_name == "bs4":
        ok = ensure_bs4()
        return True if ok else "ImportError"
    try:
        __import__(module_name)
    except Exception as exc:  # noqa: BLE001 - گزارش هر خطای ایمپورت
        return f"{type(exc).__name__}: {exc}"
    return True


#: کتابخانه‌هایی که در گزارشِ خودآزمایی بررسی می‌شوند.
PROBED_LIBRARIES = (
    "flask",
    "requests",
    "urllib3",
    "certifi",
    "bs4",
    "typing_extensions",
    "soupsieve",
)


def describe() -> dict:
    """گزارش وضعیت کتابخانه‌ها + اینکه bs4 واقعاً کار می‌کند یا نه."""
    libs: dict[str, object] = {}
    for name in PROBED_LIBRARIES:
        libs[name] = probe(name)

    # اگر typing_extensions جانشینِ خودمان باشد، در گزارش مشخص می‌شود.
    if getattr(sys.modules.get("typing_extensions"), "__frilanser_stub__", False):
        libs["typing_extensions"] = "جانشینِ داخلی (stub)"

    html_ok = False
    html_error = ""
    try:
        from frilanser.sources.base import BaseSource

        sample = BaseSource.html_to_text("<div><p>سلام &amp; درود</p></div>")
        html_ok = "سلام" in sample
        html_error = "" if html_ok else f"خروجی: {sample!r}"
    except Exception as exc:  # noqa: BLE001
        html_error = f"{type(exc).__name__}: {exc}"

    return {
        "libs": libs,
        "html_parser": {"ok": html_ok, "error": html_error},
    }
