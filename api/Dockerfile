# Backend Docker image for Railway
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies for database drivers, PDF/OCR, and table extraction
RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
     build-essential gcc g++ \
     libpq-dev libffi-dev libssl-dev \
     libmagic1 libmagic-dev \
     poppler-utils ghostscript \
     tesseract-ocr libtesseract-dev libleptonica-dev \
     libgl1 libglib2.0-0 \
     openjdk-17-jre-headless \
     curl ca-certificates \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-railway.txt .
RUN pip install --upgrade pip setuptools wheel \
  && pip install -r requirements-railway.txt

# Copy application source
COPY . .

# Ensure startup script is executable
RUN chmod +x start.sh

EXPOSE 8000

# Rely on start.sh to wire PORT and reload flags
CMD ["bash", "start.sh"]

