# --- Sybase ASE Unlock Portal: production container image ---
FROM python:3.12-slim

# Prevent .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies (build tools + unixODBC for pyodbc/FreeTDS connectivity).
# Remove build-essential afterward to keep the final image lean.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        unixodbc \
        unixodbc-dev \
        freetds-dev \
        freetds-bin \
        tdsodbc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs && \
    useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
