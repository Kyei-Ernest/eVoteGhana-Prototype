FROM python:3.12-slim

WORKDIR /app

# MySQL client tools (mysqldump) for database backups
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user; the app binds port 8000 above 1024 so no root needed.
RUN useradd --system --uid 1000 --home /app evote \
    && chown -R evote:evote /app
USER evote

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
