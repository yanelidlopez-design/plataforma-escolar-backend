# Usamos una imagen oficial de Python
FROM python:3.10-slim

# Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalamos las dependencias del sistema necesarias para MariaDB
RUN apt-get update && apt-get install -y \
    build-essential \
    libmariadb-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Instalamos las librerías principales de Django directamente
RUN pip install --no-cache-dir \
    django \
    djangorestframework \
    djangorestframework-simplejwt \
    django-cors-headers \
    django-environ \
    mysqlclient \
    drf-yasg \
    openpyxl \
    django-q2 \
    reportlab

# Copiamos el código fuente del proyecto
COPY . /app/

# Exponemos el puerto de Django
EXPOSE 8000
