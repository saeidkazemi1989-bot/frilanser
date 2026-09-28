#!/usr/bin/env bash
# اجرای دوره‌ای اسکن (برای cron یا Task Scheduler)
# مثال: هر ۳ ساعت یک‌بار
#   0 */3 * * * cd /path/to/frilanser && ./scripts/scan.sh >> logs/scan.log 2>&1

set -euo pipefail
cd "$(dirname "$0")/.."

if [ -d .pylib ]; then
  export PYTHONPATH="$PWD/.pylib:${PYTHONPATH:-}"
fi

# --online برای دریافت زنده از سایت‌ها است؛ در محیط بدون اینترنت به‌طور خودکار
# از اسنپ‌شات‌های data/raw استفاده می‌شود.
python -m frilanser run --online --demos 3 "$@"
