FROM python:3.12-slim

# Logs sin buffer (se ven al instante en `docker compose logs`) y sin .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Primero las dependencias: si solo cambia el código, esta capa se reusa
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY lento/ lento/

EXPOSE 8000

# Forma "exec" (lista JSON): python queda como PID 1 y recibe el SIGTERM de
# `docker compose stop` directamente. Con la forma "shell" lo recibiría
# /bin/sh, que no lo reenvía, y Docker terminaría matando con SIGKILL.
CMD ["python", "-m", "app.main"]
