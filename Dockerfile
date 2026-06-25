# AlphaForge API image
FROM python:3.11-slim

# build-essential lets the optional C++ risk engine compile if you enable it
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir psycopg[binary] redis yfinance

COPY . .

# default: seed synthetic data then serve the API
EXPOSE 8000
CMD ["sh", "-c", "python -m data_pipeline.ingest && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
