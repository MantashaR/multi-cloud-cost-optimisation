#!/bin/sh
set -e

wait_for_db() {
  echo "Waiting for postgres at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
  until python - <<'PY'
import os
import socket
import sys

s = socket.socket()
s.settimeout(2)
try:
    s.connect((os.environ.get("POSTGRES_HOST", "db"), int(os.environ.get("POSTGRES_PORT", "5432"))))
except OSError:
    sys.exit(1)
PY
  do
    sleep 1
  done
  echo "Postgres is up."
}

wait_for_db

case "$1" in
  web)
    python manage.py migrate --noinput
    python manage.py seed_accounts
    exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
    ;;
  worker)
    exec celery -A config worker -l info
    ;;
  beat)
    exec celery -A config beat -l info
    ;;
  *)
    exec "$@"
    ;;
esac
