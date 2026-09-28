[app]

# (str) نام برنامه که روی گوشی دیده می‌شود
title = فریلنسر یار آرنا

# (str) شناسه‌ی بسته (دامنه + نام)
package.name = frilanser
package.domain = org.arena

# (str) پوشه‌ی سورس (همین پوشه؛ فایل‌های لازم توسط CI اینجا کپی می‌شوند)
source.dir = .

# (list) پسوندهایی که بسته‌بندی می‌شوند (قالب‌های HTML و تنظیمات هم لازم‌اند)
source.include_exts = py,png,jpg,kv,atlas,html,css,js,toml,md,json,txt,svg

# (list) پوشه‌هایی که وارد APK نمی‌شوند
source.exclude_dirs = tests,.github,.git,dist,outbox,node_modules,__pycache__,.pylib,.buildozer,bin,.venv,data/cache

# (list) پوشه‌هایی که در صورت وجود حذف می‌شوند
source.exclude_patterns = */__pycache__/*,*/.pytest_cache/*

# (str) نسخه‌ی برنامه (با frilanser/version.py هماهنگ نگه دارید)
version = 1.0.0

# (list) نیازمندی‌ها: وب‌سرور Flask + کتابخانه‌های دریافت داده + پل جاوا برای نصب به‌روزرسانی
requirements = python3,flask,werkzeug,jinja2,click,itsdangerous,markupsafe,blinker,\
    requests,urllib3,idna,certifi,charset-normalizer,beautifulsoup4,soupsieve,pyjnius

# (str) جهت صفحه
orientation = portrait

# (bool) تمام‌صفحه نباشد (نوار وضعیت دیده شود)
fullscreen = 0

# --- اندروید -------------------------------------------------------------
# اینترنت برای خواندن آگهی‌ها و گرفتن به‌روزرسانی؛
# REQUEST_INSTALL_PACKAGES برای اینکه برنامه بتواند نسخه‌ی جدید خودش را نصب کند
android.permissions = INTERNET,ACCESS_NETWORK_STATE,REQUEST_INSTALL_PACKAGES,\
    READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# (int) نسخه‌ی API هدف و حداقل پشتیبانی
android.api = 34
android.minapi = 24

# (str) معماری‌ها: ابتدا فقط ۶۴بیت (پوششِ اکثر گوشی‌های امروزی)
android.archs = arm64-v8a

# (str) بوت‌استرپ webview: رابط برنامه همان صفحات وبِ سرور داخلی است
android.bootstrap = webview

# (int) پورتی که WebView به آن متصل می‌شود (با FRILANSER_PORT در main.py یکی است)
p4a.port = 5000

# (str) شاخه‌ی python-for-android
p4a.branch = develop

# (bool) در حالت اشکال‌زدایی ساخته شود (بدون نیاز به امضای توسعه‌دهنده)
android.debug = 1

# (bool) پذیرش خودکارِ پروانه‌ی SDK هنگام دانلود (برای اجرای بدون دخالت در CI)
android.accept_sdk_license = True

# --- ظاهر ---------------------------------------------------------------
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
presplash.color = #0f766e

# (str) پوشه‌ی خروجی
android.release_artifact = apk

[buildozer]

# (int) سطح لاگ (۰ خطا، ۱ اطلاعات، ۲ اشکال‌زدایی)
log_level = 2

# (int) هشدار در صورت اجرا با کاربر ریشه
warn_on_root = 0
