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
    tesseract-ocr-eng \
    fonts-liberation \
    fonts-dejavu
echo "LibreOffice installed: $(soffice --version)"

# ---------------------------------------------------------------------------
# 2. Python dependencies
# ---------------------------------------------------------------------------
echo "Installing Python dependencies..."
pip install -r requirements.txt

# ---------------------------------------------------------------------------
# 3. Static assets only. Builds must not change the application database.
# ---------------------------------------------------------------------------
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Build complete!"
