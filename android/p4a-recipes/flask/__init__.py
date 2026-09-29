"""ریسپیِ محلی برای Flask — جایگزینِ ریسپیِ داخلی python-for-android.

چرا این فایل لازم است؟
ریسپیِ داخلیِ p4a نسخه‌ی Flask **2.0.3** را نصب می‌کند و وابستگی‌های پایتونی‌اش
(به‌خصوص werkzeug) را بدون نسخه از pip می‌گیرد. نتیجه روی دستگاه این خطا بود:

    ImportError: cannot import name 'url_quote' from 'werkzeug.urls'

چون werkzeug ۳ تابع url_quote را حذف کرده و Flask قدیمی آن را وارد می‌کند.

اینجا نسخه‌ی Flask و وابستگی‌ها را با ترکیبِ تست‌شده پین می‌کنیم:
    Flask 2.2.5 + Werkzeug 2.2.3 + Jinja2 3.1.4 + itsdangerous 2.1.2 + click 8.1.7

نکته‌ی مهم: markupsafe را **بدون نسخه** می‌گذاریم تا p4a آن را با ریسپیِ خودش
(که افزونه‌ی C را برای اندروید می‌سازد) نصب کند. نوشتنِ markupsafe==x باعث
می‌شد pip بخواهد آن را نصب کند و در نهایت اصلاً نصب نشود.
"""

from pythonforandroid.recipes.flask import FlaskRecipe as _BaseRecipe


class FlaskRecipe(_BaseRecipe):
    # نسخه‌ی سازگار؛ ریسپی از آدرس زیر همان را از گیت‌هاب می‌گیرد:
    #   https://github.com/pallets/flask/archive/2.2.5.zip
    version = "2.2.5"

    # نسخه‌ی وابستگی‌ها دقیقاً پین می‌شود تا pip چیز متفاوتی نصب نکند
    python_depends = [
        "jinja2==3.1.4",
        "werkzeug==2.2.3",
        "markupsafe",      # بدون نسخه: ریسپیِ خودِ p4a آن را می‌سازد
        "itsdangerous==2.1.2",
        "click==8.1.7",
    ]


recipe = FlaskRecipe()
