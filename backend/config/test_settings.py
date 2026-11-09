"""
Test settings for pytest - uses SQLite database (a temporary file, not :memory:).

Notas importantes sobre el entorno de pruebas:
- `django.contrib.admin` se desactiva: su tabla `django_admin_log` declara una FK
  al `AUTH_USER_MODEL` (`core.Usuarios`, tabla `usuarios`), pero ese modelo está
  marcado como `managed = False` así que Django nunca crea la tabla `usuarios` en
  `migrate`. En SQLite eso provoca `foreign key mismatch` al insertar en
  `django_admin_log`. Ningún test de la suite usa el admin, por lo que es seguro
  excluirlo de las pruebas.
- Se usa un archivo temporal (no `:memory:`) para que la BD persista entre las
  distintas conexiones que abre Django/pytest-django y evitar que las tablas
  creadas en `migrate` desaparezcan al cerrar una conexión.
"""
from .settings import *

import os
import tempfile

# django.contrib.admin genera django_admin_log (FK a usuarios, managed=False).
# Se excluye de INSTALLED_APPS solo para el entorno de test. Como urls.py
# referencia admin.site.urls, se usa un ROOT_URLCONF de test sin esa ruta.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'django.contrib.admin']
ROOT_URLCONF = 'config.urls_test'

# Override database to use SQLite for tests (temporary file, shared across connections)
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

# Disable debug mode for tests
DEBUG = False

# Use a simple password hasher for faster tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Desactiva el broker de tareas asíncronas en tests (no se necesita django-q2).
Q_CLUSTER = {}
