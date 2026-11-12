"""
Test settings for pytest - uses SQLite database (a temporary file, not :memory:).

Importa de settings.py pero sobrescribe DATABASES para usar SQLite
e INSTALLED_APPS para excluir django.contrib.admin (evita FK mismatch
con django_admin_log -> usuarios managed=False).
"""
from .settings import *

import os
import tempfile
from pathlib import Path

# Django contrib.admin genera django_admin_log (FK a usuarios, managed=False).
# Se excluye de INSTALLED_APPS para evitar foreign key mismatch en SQLite.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'django.contrib.admin']
ROOT_URLCONF = 'config.urls_test'

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

# Django Q desactivado en tests
Q_CLUSTER = {}

# Frontend dist directory (para URLs de prueba)
FRONTEND_DIST_DIR = Path("frontend/dist")
