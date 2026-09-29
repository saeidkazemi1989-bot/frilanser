"""یک صفحه‌ی دانلودِ ساده برای دسترسی مستقیم (بدون نیاز به گیت‌هاب).

فایل‌ها از پوشه‌ی dist خوانده می‌شوند؛ اگر محیط آن‌ها را پاک کرده باشد،
از مخزن بازیابی می‌شوند (تابع restore_from_git).
"""

    python scripts/serve_dist.py 8000

صفحه روی http://0.0.0.0:8000 در دسترس است و فایل‌های پوشه‌ی dist را فهرست می‌کند.
"""

from __future__ import annotations

import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

LABELS = {
    "frilanser.apk": ("نسخه‌ی اندروید (APK)", "روی گوشی نصب کنید — اندروید ۷ به بالا"),
    "Frilanser-Setup.exe": ("نصب‌کننده‌ی ویندوز", "نصب کامل با آیکون در منوی شروع"),
    "frilanser-gui.exe": ("نسخه‌ی ویندوز تک‌فایل", "بدون نصب؛ دوبار کلیک و اجرا"),
    "frilanser-portable.zip": ("بسته‌ی پرتابل ویندوز", "باز کردن زیپ و اجرای frilanser-gui.exe"),
    "frilanser.exe": ("خط فرمان ویندوز", "برای کاربران حرفه‌ای"),
}


def human(size: int) -> str:
    return f"{size / 1048576:.1f} مگابایت" if size > 1048576 else f"{size / 1024:.0f} کیلوبایت"


def build_page() -> str:
    rows = []
    for path in sorted(DIST.glob("*"), key=lambda p: p.name):
        if not path.is_file() or path.suffix.lower() in (".log", ".md", ".txt"):
            continue
        title, desc = LABELS.get(path.name, (path.name, "فایل خروجی"))
        rows.append(
            f"""      <a class="item" href="/{path.name}">
        <div class="ic">{"📱" if path.suffix == ".apk" else "💾"}</div>
        <div class="txt">
          <div class="t">{title}</div>
          <div class="d">{desc}</div>
          <div class="m">{path.name} · {human(path.stat().st_size)}</div>
        </div>
        <div class="dl">دانلود</div>
      </a>"""
        )
    items = "\n".join(rows) or '<p class="empty">هنوز فایلی ساخته نشده است.</p>'
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>دانلود فریلنس‌یار آرنا</title>
<style>
  body {{ margin:0; background:#0b1220; color:#e7ecf5;
         font-family: Tahoma, "Segoe UI", system-ui, sans-serif; }}
  .wrap {{ max-width: 640px; margin: 0 auto; padding: 24px 16px 48px; }}
  h1 {{ font-size: 20px; margin: 8px 0 4px; }}
  .sub {{ color:#9fb0c9; font-size: 13px; margin-bottom: 20px; line-height: 1.9; }}
  .item {{ display:flex; gap:12px; align-items:center; background:#141c2e;
           border:1px solid #22304a; border-radius:14px; padding:12px 14px;
           margin-bottom:10px; text-decoration:none; color:inherit; }}
  .item:active {{ background:#1b2540; }}
  .ic {{ font-size:26px; }}
  .txt {{ flex:1; min-width:0; }}
  .t {{ font-weight:700; font-size:15px; }}
  .d {{ color:#9fb0c9; font-size:12.5px; margin-top:2px; }}
  .m {{ color:#6d7f9c; font-size:11.5px; margin-top:4px; direction:ltr; text-align:left; }}
  .dl {{ background:#0f766e; color:#fff; border-radius:10px; padding:8px 14px; font-size:13px; }}
  .note {{ margin-top:24px; background:#141c2e; border:1px solid #22304a;
           border-radius:14px; padding:14px; font-size:13px; line-height:2; color:#c6d3e6; }}
  .empty {{ color:#9fb0c9; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>فریلنس‌یار آرنا — دانلود مستقیم</h1>
  <div class="sub">برای نصب روی گوشی، روی «نسخه‌ی اندروید» بزنید.
  پس از دانلود، فایل را باز کنید و در صورت پیام «ناشر ناشناس» اجازه بدهید.</div>
  {items}
  <div class="note">
    <b>راهنمای نصب اندروید:</b><br>
    ۱. فایل APK را دانلود و باز کنید.<br>
    ۲. اگر پیام «Install unknown apps» آمد، اجازه را برای مرورگر فعال کنید.<br>
    ۳. برنامه را باز کنید؛ داشبورد روی خود گوشی بالا می‌آید.<br>
    ۴. از این پس برای به‌روزرسانی، دکمه‌ی «بررسی نسخه‌ی جدید» داخل برنامه کافی است.
  </div>
</div>
</body>
</html>
"""


def restore_from_git(name: str) -> bool:
    """اگر محیط فایل را پاک کرده باشد، آن را از مخزن برمی‌گرداند."""
    import subprocess

    for ref in ("FETCH_HEAD", "origin/HEAD"):
        try:
            out = subprocess.run(
                ["git", "show", f"{ref}:dist/{name}"],
                cwd=str(ROOT), capture_output=True, timeout=300,
            )
            if out.returncode == 0 and len(out.stdout) > 100_000:
                (DIST / name).write_bytes(out.stdout)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def translate_path(self, path):
        target = super().translate_path(path)
        rel = Path(target).name
        if rel and rel not in ("", "dist") and not Path(target).exists():
            restore_from_git(rel)
        return target

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = build_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"صفحه‌ی دانلود روی پورت {port} در دسترس است")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
