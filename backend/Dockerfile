FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 repopilot \
    && mkdir -p /data && chown repopilot:repopilot /data

WORKDIR /app/backend
COPY backend/ ./
COPY demo-repository/ /app/demo-repository/
RUN python -m pip install --upgrade pip && python -m pip install -c requirements.lock.txt -e .
USER repopilot
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
