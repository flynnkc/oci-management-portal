FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN groupadd -g 1001 gunicorn \
 && useradd  -u 999 -g 1001 -r -s /usr/sbin/nologin gunicorn \
 && mkdir -p /app/session \
 && chown -R gunicorn:gunicorn /app

USER gunicorn

EXPOSE 5000

CMD ["gunicorn", "-c", "gunicorn.config.py", "wsgi:app()"]
