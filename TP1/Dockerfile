FROM python:3.11-slim

# Metadatos
LABEL maintainer="Computacion II - TP1"
LABEL description="Monitor de procesos y threads - Lee /proc directamente"

# Evita prompts interactivos durante la instalación
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TERM=xterm-256color

WORKDIR /app

# Dependencias del sistema (curses ya viene con Python, rich es puro Python)
RUN apt-get update && apt-get install -y \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código fuente
COPY . .

CMD ["python", "src/main.py"]