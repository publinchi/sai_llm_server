FROM python:3.12-slim

# Evitar buffering
ENV PYTHONUNBUFFERED=1

# Establecer zona horaria
ENV TZ=America/Guayaquil

# Instalar dependencias necesarias para tzdata
RUN apt-get update && \
    apt-get install -y --no-install-recommends tzdata && \
    ln -snf /usr/share/zoneinfo/"$TZ" /etc/localtime && \
    echo "$TZ" > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

# Carpeta de trabajo
WORKDIR /app

# Instalar litellm con extras proxy y requests
RUN pip install --no-cache-dir "litellm[proxy]" requests

# Copiar archivos
COPY sai_handler.py .
COPY config.yaml .

# CMD para iniciar litellm con tu config
CMD ["litellm", "--config", "config.yaml"]
