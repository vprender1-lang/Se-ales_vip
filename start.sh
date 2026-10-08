#!/usr/bin/env bash
set -o errexit

python manage.py migrate
python manage.py telegram_set_webhook || true

# Motor automático deshabilitado: las señales se publican solo manualmente.

exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000}
