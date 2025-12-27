# Usar una imagen base ligera de Python
FROM python:3.11-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la aplicación
COPY . .

# Crear un usuario no-root para mayor seguridad
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Exponer el puerto que usará la aplicación
# (ajusta según tu bot, comúnmente 8080, 3000, etc.)
EXPOSE 8080

# Comando para ejecutar el bot
# AJUSTA ESTO según tu bot específico:
# Para bots de Discord/Python: python bot.py
# Para bots de Telegram: python main.py
# Para bots web: gunicorn app:app --bind 0.0.0.0:8080
CMD ["python", "bot.py"]
