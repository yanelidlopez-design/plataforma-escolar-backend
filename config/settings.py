import os
from pathlib import Path
import drf_yasg 
import sys
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')

# Token secreto del webhook de Google Forms (cabecera X-Webhook-Token).
# Si no está definido, el webhook rechaza todas las peticiones con 403.
WEBHOOK_SECRET_TOKEN = env('WEBHOOK_SECRET_TOKEN', default='')

# ALLOWED_HOSTS: Lee desde variable de entorno como string separado por comas
# Ejemplo: ALLOWED_HOSTS=localhost,127.0.0.1,tudominio.com
allowed_hosts_str = env('ALLOWED_HOSTS', default='')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_str.split(',') if host.strip()] if allowed_hosts_str else []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'drf_yasg',
    'rest_framework',
    'corsheaders',

    # Local apps
    'apps.core.apps.CoreConfig',
    'apps.personal.apps.PersonalConfig',
    'apps.academico.apps.AcademicoConfig',
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

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Busca aquí tu nuevo archivo
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

# Configuración de Base de Datos MariaDB / MySQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # JWT (frontend envía Authorization: Bearer <access>)
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        # Sesión/Basic para el browsable API y el admin de Django
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
}

# CORS_ALLOWED_ORIGINS: Lee desde variable de entorno como string separado por comas
# Ejemplo: CORS_ALLOWED_ORIGINS=http://localhost:3000,https://tufrontend.com
cors_origins_str = env('CORS_ALLOWED_ORIGINS', default='')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_str.split(',') if origin.strip()] if cors_origins_str else []
CORS_ALLOW_ALL_ORIGINS = False

LANGUAGE_CODE = 'es-es'

TIME_ZONE = 'America/Caracas'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

SWAGGER_SETTINGS = {
    'USE_SESSION_AUTH': True,
    'VALIDATOR_URL': None,  # Desactiva la validación externa que rompe en entornos locales
}


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
