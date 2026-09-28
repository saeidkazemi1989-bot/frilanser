"""عیب‌یابی خودکار: چرا داده نمی‌آید؟

گزارش می‌کند که کدام بخش مشکل دارد: نبودِ اسنپ‌شات، مسدود بودن سایت‌ها،
نوشته نشدنِ خروجی، یا خالی بودنِ پایگاه داده. خروجی هم چاپ می‌شود و هم در
`outbox/doctor.txt` ذخیره می‌گردد (برای فرستادن به پشتیبانی).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from .config import BUNDLE, ROOT


def _probe_source(source, timeout: float = 6.0) -> tuple[bool, str]:
    """تلاش برای گرفتن فهرست یک منبع؛ فقط برای تشخیص، بدون ذخیره."""
    import urllib.error
    import urllib.request

    urls = []
    getter = getattr(source, "list_urls", None)
    if callable(getter):
        try:
            urls = [u for u in getter() if u]
        except Exception:  # noqa: BLE001
            urls = []
    if not urls:
        urls = [source.scfg.get("url") or source.scfg.get("list_url") or ""]
    url = urls[0]
    if not url:
        return False, "آدرسی در تنظیمات تعریف نشده"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) frilanser/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read(200_000).decode("utf-8", "ignore")
            return True, f"پاسخ {resp.status} ({len(body):,} بایت)"
    except urllib.error.HTTPError as exc:
        return False, f"خطای HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"دسترسی ندارد ({exc.reason})"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def run_doctor(cfg, store, check_network: bool = True, timeout: float = 6.0) -> str:
    lines: list[str] = []
    add = lines.append

    add("=" * 66)
    add("گزارش عیب‌یابی فریلنس‌یار آرنا — " + datetime.now().strftime("%Y/%m/%d %H:%M"))
    add("=" * 66)

    # ۱. محیط اجرا
    add("")
    add("۱. محیط اجرا")
    add(f"   اجرای فایل exe : {bool(getattr(sys, 'frozen', False))}")
    add(f"   مسیر اجرا      : {sys.executable}")
    add(f"   پوشه‌ی داده‌ها : {ROOT}")
    add(f"   باندل برنامه   : {BUNDLE}")
    add(f"   فایل تنظیمات   : {cfg.path} {'✓' if Path(cfg.path).exists() else '✗ وجود ندارد'}")
    for name, path in (("داده‌ها", cfg.data_dir), ("اسنپ‌شات‌ها", cfg.raw_dir),
                       ("خروجی", cfg.outbox_dir), ("دموها", cfg.demo_dir)):
        ok = "✓" if Path(path).exists() else "✗"
        try:
            count = len(list(Path(path).iterdir()))
        except OSError:
            count = 0
        add(f"   پوشه‌ی {name:<9}: {path} {ok} ({count} مورد)")

    writable = os.access(str(ROOT), os.W_OK)
    add(f"   قابل نوشتن؟    : {'بله ✓' if writable else 'خیر ✗ (خروجی‌ها ذخیره نمی‌شوند!)'}")

    # ۲. اسنپ‌شات‌ها (منبع آفلاین داده)
    add("")
    add("۲. اسنپ‌شات‌های آفلاین (منبع اصلی وقتی اینترنت در دسترس نیست)")
    raw = Path(cfg.raw_dir)
    snaps = sorted(raw.glob("*")) if raw.exists() else []
    if snaps:
        for s in snaps:
            add(f"   ✓ {s.name} ({s.stat().st_size:,} بایت)")
    else:
        add("   ✗ هیچ اسنپ‌شاتی در پوشه‌ی data/raw نیست!")
        if BUNDLE != ROOT and (Path(BUNDLE) / "data" / "raw").exists():
            bundled = list((Path(BUNDLE) / "data" / "raw").iterdir())
            add(f"   → {len(bundled)} اسنپ‌شات داخل برنامه هست و باید کپی می‌شد؛"
                f" کپی خودکار دوباره انجام می‌شود.")
            try:
                raw.mkdir(parents=True, exist_ok=True)
                for item in bundled:
                    if item.is_file():
                        import shutil
                        shutil.copy2(item, raw / item.name)
                add(f"   ✓ اسنپ‌شات‌ها بازیابی شدند ({len(list(raw.iterdir()))} فایل)")
            except Exception as exc:  # noqa: BLE001
                add(f"   ✗ خطا در بازیابی: {exc}")

    # ۳. پایگاه داده
    add("")
    add("۳. وضعیت داده‌ها")
    projects = store.all()
    add(f"   تعداد پروژه‌ها : {len(projects)}")
    if projects:
        verdicts: dict[str, int] = {}
        for p in projects:
            v = p.verdict or "بدون غربالگری"
            verdicts[v] = verdicts.get(v, 0) + 1
        for k, v in verdicts.items():
            add(f"     · {k}: {v}")
        demo_count = sum(1 for p in projects if p.demo)
        add(f"   پیش‌نمایش ساخته‌شده: {demo_count}")
    else:
        add("   → هنوز هیچ آگهی‌ای جمع‌آوری نشده است. یک بار «اجرای کامل» را بزنید.")

    # ۴. دسترسی به سایت‌ها
    add("")
    add("۴. دسترسی به سایت‌های فریلنسری" + (" (در حال بررسی…)" if check_network else " (رد شده)"))
    if not check_network:
        add("   برای بررسی، دستور را بدون --offline اجرا کنید.")
        reachable = None
    else:
        from .sources.registry import build_sources

        sources = build_sources(cfg)
        reachable = 0
        for key, source in sources.items():
            ok, msg = _probe_source(source, timeout=timeout)
            reachable += 1 if ok else 0
            add(f"   {'✓' if ok else '✗'} {key}: {msg}")
        add("")
        if reachable:
            add(f"   نتیجه: {reachable} از {len(sources)} منبع در دسترس است"
                f" → می‌توانید از «دریافت زنده» استفاده کنید.")
        else:
            add("   نتیجه: هیچ‌کدام از سایت‌ها از این شبکه در دسترس نیستند")
            add("   (فیلتر/تحریم/نیاز به VPN یا دسترسی مستقیم از ایران).")
            add("   برنامه به‌طور خودکار از اسنپ‌شات‌های داخلی استفاده می‌کند؛")
            add("   برای داده‌ی تازه، یکی از این کارها را انجام دهید:")
            add("     · با VPN/فیلترشکن متصل شوید و دوباره «دریافت زنده» را بزنید، یا")
            add("     · فایل‌های خام هر سایت را در پوشه‌ی data/raw بگذارید")

    # ۵. نتیجه‌گیری و پیشنهاد
    add("")
    add("۵. پیشنهاد")
    if not projects:
        if snaps or (BUNDLE != ROOT and (Path(BUNDLE) / "data" / "raw").exists()):
            add("   → دکمه‌ی «اجرای کامل» را بزنید (بدون اینترنت هم از اسنپ‌شات‌ها می‌خواند).")
        else:
            add("   → اسنپ‌شاتی وجود ندارد و اینترنت هم در دسترس نیست؛")
            add("     با VPN دوباره امتحان کنید یا شبکه‌ی دیگری را تست کنید.")
    elif reachable == 0 and check_network:
        add("   → داده‌ها از اسنپ‌شات ساخته شده‌اند؛ برای به‌روزرسانی از VPN استفاده کنید.")
    else:
        add("   → به نظر همه چیز درست است؛ در صورت مشکل این فایل را برای من بفرستید.")

    text = "\n".join(lines)
    try:
        out = Path(cfg.outbox_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "doctor.txt").write_text(text, encoding="utf-8")
    except OSError:
        pass
    return text
