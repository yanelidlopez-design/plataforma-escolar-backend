"""
Test settings for pytest - uses SQLite database (a temporary file, not :memory:).

Este archivo es COMPLETAMENTE INDEPENDIENTE de settings.py para evitar problemas
con MySQL en el entorno de CI/CD. No importa de .settings para prevenir errores
de conexión a base de datos remota.
"""

import os
import tempfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get('SECRET_KEY', 'test-secret-key-ci')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',  # Necesario para las URLs aunque managed=False
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_yasg',
    'corsheaders',
    'django_q',
    'apps.core',
    'apps.personal',
    'apps.academico',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls_test'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# SQLite para tests - archivo temporal compartido entre conexiones
TEST_DB_NAME = os.environ.get(
    'TEST_DB_NAME',
    os.path.join(tempfile.gettempdir(), 'plataforma_test.sqlite3'),
)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': TEST_DB_NAME,
        'TEST': {'NAME': TEST_DB_NAME},
    }
}

# Password hashing rápido para tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Internacionalización
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/Caracas'
USE_I18N = True
USE_TZ = True

# Archivos estáticos
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django Q desactivado en tests
Q_CLUSTER = {}

# Emails en consola para tests
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

# JWT
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
}

# Modelo de usuario personalizado
AUTH_USER_MODEL = 'core.Usuarios'

# URLs de test (sin admin para evitar FK mismatch)
ROOT_URLCONF = 'config.urls_test'

# Frontend dist directory (para URLs de prueba)
from pathlib import Path
FRONTEND_DIST_DIR = Path("frontend/dist")
