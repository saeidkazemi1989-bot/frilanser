@echo off
REM ساخت فایل اجرایی ویندوز (frilanser.exe) به صورت محلی
REM پیش‌نیاز: پایتون ۳.۱۰ یا بالاتر
REM خروجی: dist\frilanser.exe

echo == نصب ابزارها ==
python -m pip install --upgrade pip
python -m pip install pyinstaller Flask requests beautifulsoup4

echo == ساخت EXE ==
pyinstaller --noconfirm --onefile --console --name frilanser ^
  --add-data "config.toml;." ^
  --add-data "frilanser\web\templates;frilanser\web\templates" ^
  --add-data "frilanser\web\static;frilanser\web\static" ^
  --add-data "data\raw;data\raw" ^
  --add-data "README.md;." ^
  --hidden-import flask --hidden-import jinja2 --hidden-import werkzeug ^
  --hidden-import bs4 --hidden-import requests ^
  frilanser\__main__.py

echo.
echo تمام شد. فایل اجرایی اینجاست: dist\frilanser.exe
echo نمونه استفاده:
echo   frilanser.exe run
echo   frilanser.exe serve --open
echo   frilanser.exe needs --full
pause
