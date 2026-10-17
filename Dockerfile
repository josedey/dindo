FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 DINDO_DATA_DIR=/app/data

RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dindo ./dindo
COPY docs ./docs
COPY demo ./demo

# Build the demo database (synthetic cases filled from their ground truth so the app works before any upload)
RUN python -m dindo.servidor.seed --gt

EXPOSE 8000
CMD ["sh", "-c", "uvicorn dindo.servidor.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
