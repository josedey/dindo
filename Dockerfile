FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 DINDO_DATA_DIR=/app/data

RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dindo ./dindo
COPY docs ./docs
COPY demo ./demo

# Demo database: what the AMD models read from the anonymized demo documents (tools/exportar_db_demo.py).
# Without it, fall back to filling the demo cases from their hand transcription.
RUN mkdir -p data && if [ -f demo/dindo_demo.db ]; then cp demo/dindo_demo.db data/dindo.db; else python -m dindo.servidor.seed --gt; fi

# The demo case is from 2022: replay one of its days, mid-afternoon
ENV DINDO_TODAY=2022-10-17 DINDO_TIME=15:10

EXPOSE 8000
CMD ["sh", "-c", "uvicorn dindo.servidor.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
