import sys

from .cli import main

# خطاهای پیش‌بینی‌نشده را با پیامی خوانا نشان می‌دهیم (در نسخه‌ی EXE پنجره سریع بسته می‌شود)
if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nاجرا لغو شد.")
        sys.exit(130)
