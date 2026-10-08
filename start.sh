#!/usr/bin/env bash
set -o errexit

python manage.py migrate
python manage.py telegram_set_webhook || true

if [ "${SIGNAL_BACKGROUND_WORKER:-1}" = "1" ]; then
  python manage.py signal_worker --interval "${SIGNAL_WORKER_INTERVAL:-2}" --limit "${SIGNAL_WORKER_LIMIT:-200}" &
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000}
