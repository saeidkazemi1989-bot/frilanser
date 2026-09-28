# گزارش تست نسخه‌ی اجرایی ویندوز (frilanser.exe)

خروجی exit=0 به‌معنی اجرای موفق است.

## frilanser.exe --help
```
usage: frilanser [-h] [--config CONFIG]
                 {run,scan,screen,propose,demo,report,list,show,needs,decide,serve}
                 ...

فریلنس‌یار آرنا — پیدا کردن و غربال کردن پروژه‌های فریلنسری ایرانی

positional arguments:
  {run,scan,screen,propose,demo,report,list,show,needs,decide,serve}
    run                 اجرای کامل خط لوله
    scan                جمع‌آوری آگهی‌ها
    screen              غربالگری پروژه‌ها
    propose             قیمت‌گذاری
    demo                ساخت دمو
    report              ساخت گزارش و صف نیاز به ورود شما
    list                فهرست پروژه‌ها
    show                نمایش جزئیات یک پروژه
    needs               کارهایی که باید خودتان انجام دهید
    decide              ثبت تصمیم شما
    serve               اجرای داشبورد وب

options:
  -h, --help            show this help message and exit
  --config CONFIG       مسیر فایل تنظیمات (پیش‌فرض config.toml)
help_exit=0
```

## frilanser.exe run --demos 1
```
— جمع‌آوری آگهی‌ها…
  0 آگهی (0 جدید)
— غربالگری (آیا در آرنا قابل اجراست؟)…
  کاندیدا: 0 | بررسی: 0 | رد: 0
— ساخت دمو برای بهترین گزینه‌ها…
— قیمت‌گذاری…
— گزارش و اعلان‌ها…

======================================================================
گزارش: D:\a\_temp\exetest\outbox\reports\2026-09-28.md
کارهایی که باید خودتان انجام دهید: 0 مورد
run_exit=0
```

## فایل‌های تولیدشده توسط EXE
```
.:
data
outbox

./data:
activity.json
cache
needs_you.json
projects.json
raw

./data/cache:

./data/raw:

./outbox:
reports

./outbox/reports:
2026-09-28.md
latest.md
```
