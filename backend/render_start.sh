#!/usr/bin/env bash
set -euo pipefail

# These must exist in the running image, not just a temporary build machine.
command -v soffice >/dev/null || { echo "LibreOffice is missing; deploy backend/Dockerfile." >&2; exit 1; }
command -v tesseract >/dev/null || { echo "Tesseract is missing; deploy backend/Dockerfile." >&2; exit 1; }
python manage.py migrate --check

case "${1:-web}" in
  web)
    python manage.py collectstatic --noinput
    exec daphne -b 0.0.0.0 -p "${PORT:-8000}" backend.asgi:application
    ;;
  worker)
    exec celery -A backend worker --loglevel=info --concurrency=2
    ;;
  scheduler)
    # Exactly one scheduler instance. Durable notification dedupe lives in Postgres.
    exec celery -A backend beat --loglevel=info --schedule=/tmp/emby-celerybeat
    ;;
  *) echo "Expected web, worker or scheduler." >&2; exit 2 ;;
esac
