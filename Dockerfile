# Dockerfile para Bot de Subida a Revistas

# ===== ETAPA 1: CONSTRUCCIÓN =====
FROM python:3.10-slim as builder

# Instalar dependencias del sistema para compilación
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Crear entorno virtual
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir -r requirements.txt

# Instalar pymegatools desde GitHub si no está en requirements
RUN pip install --no-cache-dir git+https://github.com/keepcosmos/pymegatools.git

# ===== ETAPA 2: EJECUCIÓN =====
FROM python:3.10-slim as runner

# Instalar dependencias del sistema necesarias en runtime
RUN apt-get update && apt-get install -y \
    # Para descargas Mega
    megatools \
    # Para comprimir/descomprimir
    zip \
    unzip \
    p7zip-full \
    # Para YouTube-DL
    ffmpeg \
    # Utilidades del sistema
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no root para seguridad
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app && chown -R botuser:botuser /app

# Copiar entorno virtual desde builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Establecer variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TZ=UTC

# Configurar directorio de trabajo
WORKDIR /app
USER botuser

# Copiar archivos de la aplicación
COPY --chown=botuser:botuser . .

# Crear directorios necesarios
RUN mkdir -p downloads configs logs && \
    chmod +x /app/*.py

# Exponer puerto (Railway necesita esto aunque sea un bot)
EXPOSE 10000

# Script de inicio saludable para Railway
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:10000/health || exit 1

# Comando para mantener el contenedor activo (Railway necesita un proceso persistente)
CMD ["run.sh", "bash.sh"]
