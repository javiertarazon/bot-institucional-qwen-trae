# Dockerfile para CIP Lite - Imagen oficial y segura
FROM python:3.12-slim-bookworm AS builder

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias de Python
COPY cip-lite/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Etapa de producción
FROM python:3.12-slim-bookworm AS production

# Crear usuario no root para seguridad
RUN useradd -m -u 1000 cip

# Copiar dependencias de la etapa builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Establecer directorio de trabajo
WORKDIR /app
RUN chown -R cip:cip /app

# Copiar código fuente
COPY --chown=cip:cip cip-lite/ .

# Variables de entorno seguras
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PROMETHEUS_PORT=8000

# Usuario no root
USER cip

# Exponer puertos
EXPOSE 8501 8000

# Comando de inicio
CMD ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
