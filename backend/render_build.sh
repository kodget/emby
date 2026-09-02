#!/usr/bin/env bash
# exit on error
set -o errexit

# ---------------------------------------------------------------------------
# 1. System dependencies
# ---------------------------------------------------------------------------
echo "Installing system packages (LibreOffice, poppler)..."
apt-get update -qq
# LibreOffice — converts PPTX/DOCX → PDF for slide rendering
# poppler-utils — pdfinfo / pdfimages used by some PDF extraction paths
apt-get install -y --no-install-recommends \
    libreoffice \
    libreoffice-calc \
    libreoffice-impress \
    libreoffice-writer \
    poppler-utils \
    fonts-liberation \
    fonts-dejavu
echo "LibreOffice installed: $(soffice --version)"

# ---------------------------------------------------------------------------
# 2. Python dependencies
# ---------------------------------------------------------------------------
echo "Installing Python dependencies..."
pip install -r requirements.txt

# ---------------------------------------------------------------------------
# 3. Django setup
# ---------------------------------------------------------------------------
echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Ensuring superuser exists..."
python manage.py create_admin

echo "Seeding gamification achievements..."
python manage.py seed_gamification

echo "Build complete!"
