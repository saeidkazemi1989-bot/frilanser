"""نقطه‌ی ورودِ نسخه‌ی اجرایی (EXE) برای ویندوز.

PyInstaller فایل ورودی را به‌عنوان اسکریپت سطح‌بالا اجرا می‌کند، بنابراین اینجا
حتماً باید از import مطلق استفاده شود (import نسبی در آن حالت خطا می‌دهد).
"""

import sys

from frilanser.cli import main

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nاجرا لغو شد.")
        sys.exit(130)
