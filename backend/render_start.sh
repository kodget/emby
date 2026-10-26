#!/usr/bin/env bash
set -euxo pipefail

cd -- "$(dirname -- "$0")"

echo "render_start.sh called with argument: ${1:-NONE}"

# Combined mode: run supervisor immediately (skip system checks - preflight handles them)
if [ "${1:-web}" = "combined" ]; then
  echo "Combined mode detected, starting supervisor"
  exec python render_supervisor.py
fi

echo "Not combined mode, running system checks"

# These must exist in the running image, not just a temporary build machine.
command -v soffice >/dev/null || { echo "LibreOffice is missing; deploy backend/Dockerfile." >&2; exit 1; }
command -v tesseract >/dev/null || { echo "Tesseract is missing; deploy backend/Dockerfile." >&2; exit 1; }
python manage.py migrate --check

case "${1:-web}" in
  web)
    python manage.py collectstatic --noinput
    # Use Gunicorn with 4 workers for better concurrency on free tier
    # Gevent workers handle async I/O without blocking
    exec gunicorn backend.wsgi:application \
      --bind "0.0.0.0:${PORT:-8000}" \
      --workers 4 \
      --worker-class gevent \
      --worker-connections 1000 \
      --timeout 120 \
      --keep-alive 5 \
      --log-level info
    ;;
  worker)
    exec celery -A backend worker --loglevel=info --concurrency=2
    ;;
  scheduler)
    # Exactly one scheduler instance. Durable notification dedupe lives in Postgres.
    exec celery -A backend beat --loglevel=info --schedule=/tmp/emby-celerybeat \
      --scheduler=backend.singleton_beat:SingletonScheduler
    ;;
  *) echo "Expected combined, web, worker or scheduler." >&2; exit 2 ;;
esac
