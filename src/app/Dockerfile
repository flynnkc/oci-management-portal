FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && pip install -r requirements.txt && rm requirements.txt && \
addgroup --gid 1001 --system app && adduser --no-create-home --shell /bin/false \
--disabled-password --uid 999 --system --group app

COPY update.py /app/
COPY modules /app/modules/

USER app

ENTRYPOINT ["gunicorn"]
