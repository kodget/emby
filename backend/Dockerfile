FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-impress libreoffice-writer libreoffice-calc \
    poppler-utils tesseract-ocr tesseract-ocr-eng \
    fonts-liberation fonts-dejavu libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
RUN useradd --create-home emby && chown -R emby:emby /app
USER emby
CMD ["bash", "render_start.sh", "web"]
