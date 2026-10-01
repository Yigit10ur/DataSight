FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

RUN useradd --system --no-create-home --uid 10001 datasight \
    && mkdir /data && chown 10001:10001 /data
# Accounts live in a SQLite file here. A volume mounted on /data starts out owned
# by this user, so the server can write to it although the rest is read-only.
VOLUME /data
ENV DATASIGHT_DATABASE_PATH=/data/datasight.db
USER 10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]

# One worker: datasets live in process memory and are not shared between workers.
# --limit-concurrency answers 503 instead of queueing work without bound.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", \
     "--limit-concurrency", "32", \
     "--timeout-keep-alive", "5", \
     "--no-server-header"]
