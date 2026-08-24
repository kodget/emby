#!/bin/bash

# Deployment script for quiz examination system
# Handles zero-downtime migration for model extensions

set -e

echo "Starting quiz examination system deployment..."

# Environment checks
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL not set"
    exit 1
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "ERROR: GEMINI_API_KEY not set"
    exit 1
fi

echo "Environment checks passed."

# Create backup
echo "Creating database backup..."
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
pg_dump $DATABASE_URL > $BACKUP_FILE
echo "Database backup created: $BACKUP_FILE"

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Check migration success
if [ $? -ne 0 ]; then
    echo "ERROR: Migration failed! Rolling back..."
    # Restore from backup if needed
    echo "Please restore from backup: $BACKUP_FILE"
    exit 1
fi

echo "Migrations completed successfully."

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Restart services
echo "Restarting application services..."

# Restart Celery workers (adjust command based on your deployment)
if command -v supervisorctl &> /dev/null; then
    supervisorctl restart celery-worker
    supervisorctl restart celery-beat
elif command -v systemctl &> /dev/null; then
    systemctl restart celery-worker
    systemctl restart celery-beat
else
    echo "WARNING: Could not restart Celery services automatically"
    echo "Please restart Celery workers and beat manually"
fi

# Restart web application (adjust based on your deployment)
if command -v supervisorctl &> /dev/null; then
    supervisorctl restart gunicorn
elif command -v systemctl &> /dev/null; then
    systemctl restart gunicorn
else
    echo "WARNING: Could not restart web application automatically"
    echo "Please restart your web application manually"
fi

# Warm up cache
echo "Warming up application cache..."
python manage.py shell -c "
from curriculum.optimizations import cache_question_counts
cache_question_counts()
print('Cache warmed up successfully')
"

# Health check
echo "Running post-deployment health check..."
python manage.py check --deploy

if [ $? -eq 0 ]; then
    echo "✅ Deployment completed successfully!"
    echo "Backup file: $BACKUP_FILE"
else
    echo "❌ Health check failed! Please investigate."
    exit 1
fi

echo "Quiz examination system deployment complete."