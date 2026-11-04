#!/bin/sh
set -eu

python manage.py ensure_legacy_schema
python manage.py migrate --noinput
exec "$@"
