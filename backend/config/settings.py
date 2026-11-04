from pathlib import Path
import drf_yasg
import sys
import environ
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / 'backend'
FRONTEND_DIST_DIR = BASE_DIR / 'frontend' / 'dist'

sys.path.insert(0, str(BACKEND_DIR))

env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(BASE_DIR / '.env')

DEBUG = env.bool('DEBUG', default=False)
SECRET_KEY = env(
    'DJANGO_SECRET_KEY',
    default=env('SECRET_KEY', default=''),
)
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-local-development-only'
    else:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY debe configurarse en producción.')

# Token secreto del webhook de Google Forms (cabecera X-Webhook-Token).
# Si no está definido, el webhook rechaza todas las peticiones con 403.
WEBHOOK_SECRET_TOKEN = env('WEBHOOK_SECRET_TOKEN', default='')

# ALLOWED_HOSTS: Lee desde variable de entorno como string separado por comas
# Ejemplo: ALLOWED_HOSTS=localhost,127.0.0.1,tudominio.com
allowed_hosts_str = env('ALLOWED_HOSTS', default='')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_str.split(',') if host.strip()] if allowed_hosts_str else []
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured('ALLOWED_HOSTS debe configurarse en producción.')
# Permite las comprobaciones internas del servicio y el acceso local de desarrollo.
if DEBUG:
    ALLOWED_HOSTS.extend(
        host for host in ('localhost', '127.0.0.1', 'web') if host not in ALLOWED_HOSTS
    )

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
    'django_q',

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
        'DIRS': [BACKEND_DIR / 'templates'],
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

# MariaDB usa el backend MySQL de Django. Convierte el esquema de URL para que
# la configuración funcione también con versiones de dj-database-url sin alias mariadb.
database_url = env('DATABASE_URL', default='')
if database_url:
    if database_url.startswith('mariadb://'):
        database_url = f'mysql://{database_url.removeprefix("mariadb://")}'
    DATABASES = {
        'default': dj_database_url.parse(
            database_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    legacy_database_values = ('DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT')
    if not all(env(key, default='') for key in legacy_database_values):
        raise ImproperlyConfigured(
            'Configura DATABASE_URL o todas las variables DB_NAME, DB_USER, '
            'DB_PASSWORD, DB_HOST y DB_PORT.'
        )
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

DATABASES['default'].setdefault('OPTIONS', {})
DATABASES['default']['OPTIONS'].setdefault('charset', 'utf8mb4')
DATABASES['default']['OPTIONS'].setdefault(
    'init_command',
    "SET sql_mode='STRICT_TRANS_TABLES'",
)


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
        # JWT contra core.Usuarios (acepta Authorization: Bearer o la cookie
        # HttpOnly 'access_token' que emite el login). Ver apps.core.authentication.
        'apps.core.authentication.UsuariosJWTAuthentication',
        # Sesión/Basic para el browsable API y el admin de Django
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
}

# CORS_ALLOWED_ORIGINS: Lee desde variable de entorno como string separado por comas
# Ejemplo: CORS_ALLOWED_ORIGINS=http://localhost:3000,https://tufrontend.com
cors_origins_str = env('CORS_ALLOWED_ORIGINS', default='')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_str.split(',') if origin.strip()] if cors_origins_str else []
# Agregar orígenes por defecto solo en desarrollo local.
if DEBUG and not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://192.168.1.8:3000',
    ]
# Usado junto con CORS_ALLOWED_ORIGINS para que el navegador acepte
# cookies (p. ej. 'access_token') en peticiones cross-origin.
CORS_ALLOW_CREDENTIALS = True
# CORS_ALLOW_ALL_ORIGINS deshabilitado: se mantiene la lista explícita
# en CORS_ALLOWED_ORIGINS junto con CORS_ALLOW_CREDENTIALS = True para
# evitar rechazos de CORS en navegadores con credenciales (cookies/token).
# CORS_ALLOW_ALL_ORIGINS = True

csrf_origins_str = env('CSRF_TRUSTED_ORIGINS', default='')
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in csrf_origins_str.split(',') if origin.strip()
]
if not DEBUG and not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured('CSRF_TRUSTED_ORIGINS debe configurarse en producción.')

SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=not DEBUG)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=not DEBUG)
if not DEBUG:
    # El backend solo debe estar accesible a través del proxy HTTPS de producción.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31_536_000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
        'SECURE_HSTS_INCLUDE_SUBDOMAINS',
        default=False,
    )
    SECURE_CONTENT_TYPE_NOSNIFF = True

LANGUAGE_CODE = 'es-es'

TIME_ZONE = 'America/Caracas'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'
STATICFILES_DIRS = [FRONTEND_DIST_DIR]

# Archivos de usuario (exportaciones generadas en segundo plano por django-q2)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Cola de tareas asíncronas (Misión 10): broker basado en ORM (sin Redis).
# Consumo mínimo para entorno local de 8GB: 2 workers, bulk=1.
# El worker se ejecuta con: python manage.py qcluster
Q_CLUSTER = {
    'name': 'plataforma_escolar',
    'workers': 2,
    'timeout': 300,          # 5 min máximo por reporte
    'retry': 360,
    'queue_limit': 50,
    'bulk': 1,
    'orm': 'default',        # broker = base de datos de Django
    'label': 'Django Q',
    'save_limit': 250,
    'catch_up': False,
}

SWAGGER_SETTINGS = {
    'USE_SESSION_AUTH': True,
    'VALIDATOR_URL': None,  # Desactiva la validación externa que rompe en entornos locales
}


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    default=(
        'django.core.mail.backends.console.EmailBackend'
        if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'
    ),
)
EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
DEFAULT_FROM_EMAIL = env(
    'DEFAULT_FROM_EMAIL',
    default=EMAIL_HOST_USER or 'noreply@localhost',
)
FRONTEND_URL = env(
    'FRONTEND_URL',
    default='http://localhost:5173' if DEBUG else '',
)
PASSWORD_RESET_TIMEOUT = 60 * 60

REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    **REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}),
    'password_reset': '5/hour',
}
