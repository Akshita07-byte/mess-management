#!/usr/bin/env bash
set -e
python manage.py migrate --noinput
python manage.py seed_demo
exec gunicorn config.wsgi --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120
