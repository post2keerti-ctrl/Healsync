FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV PYTHONPATH=/app/src
CMD ["sh", "-c", "exec uvicorn healsync_backend.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8080}"]
