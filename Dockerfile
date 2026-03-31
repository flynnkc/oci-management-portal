FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY src/requirements.txt ./

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
 && /opt/venv/bin/pip check

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN groupadd -g 1001 gunicorn \
 && useradd -u 999 -g 1001 -r -s /usr/sbin/nologin gunicorn

COPY --from=builder /opt/venv /opt/venv

COPY --chown=gunicorn:gunicorn src/ .

USER gunicorn

EXPOSE 5000

CMD ["gunicorn", "-c", "gunicorn.config.py", "wsgi:app"]