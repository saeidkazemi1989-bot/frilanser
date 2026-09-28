#!/usr/bin/env bash
# نصب وابستگی‌ها در پوشه‌ی .pylib داخل پروژه (قابل حمل، بدون نیاز به دسترسی ریشه)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "→ نصب وابستگی‌ها در .pylib ..."
python3 -m pip install --break-system-packages --target .pylib \
  Flask requests beautifulsoup4 pytest

echo "→ بررسی نصب"
PYTHONPATH="$PWD/.pylib" python3 -c "import flask, requests, bs4; print('deps ok')"

echo "→ اجرای تست‌ها"
PYTHONPATH="$PWD/.pylib" python3 -m pytest tests -q

echo
echo "تمام شد. برای اجرا:"
echo "  PYTHONPATH=\$PWD/.pylib python -m frilanser run"
echo "  PYTHONPATH=\$PWD/.pylib python -m frilanser serve"
