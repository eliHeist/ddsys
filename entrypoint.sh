#!/bin/bash
set -e

python manage.py migrate
python manage.py createcachetable  # the shared cache table (dbcache); does nothing if it exists
python manage.py seed_basics

# First admin: set DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD on the first deploy.
if [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
    python manage.py createsuperuser --noinput || true
fi

python manage.py collectstatic --noinput

# Async Django: serve ASGI with uvicorn
exec uvicorn dakdot.asgi:application --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips='*'
