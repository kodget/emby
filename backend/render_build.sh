#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run create_admin command (idempotent; safely skips if user exists)
echo "Ensuring superuser exists..."
python manage.py create_admin
