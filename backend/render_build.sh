#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run create_admin only if explicitly requested to prevent unnecessary execution on every deploy
if [ "$RENDER_CREATE_SUPERUSER" = "True" ]; then
    echo "Creating superuser..."
    python manage.py create_admin
    echo "Superuser creation step completed. You may now remove RENDER_CREATE_SUPERUSER or set it to False."
else
    echo "Skipping superuser creation. Set RENDER_CREATE_SUPERUSER=True to run."
fi
