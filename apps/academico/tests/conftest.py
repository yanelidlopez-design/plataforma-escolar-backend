"""
Fixtures compartidas de los tests del academico.

Los modelos legacy (managed=False) no se crean por las migraciones, así que
este fixture genera sus tablas en la BD de test (SQLite en memoria) antes de
cada test.

Usa `transactional_db` (TransactionTestCase) en vez de `db`: SQLite no permite
desactivar las FK constraints dentro de un bloque atómico, y el schema_editor
lo exige al entrar. El teardown lo hace pytest-django con el flush.
"""
import pytest
from django.db import connection

from apps.academico.models import Alumnos
from apps.core.models import Direcciones, Usuarios
from apps.personal.models import AlumnoRepresentante, Profesores, RepresentantesLegales

# Orden: primero las referenciadas por FK de las demás.
MODELOS_LEGACY = [
    Usuarios,
    Direcciones,
    Profesores,
    RepresentantesLegales,
    Alumnos,
    AlumnoRepresentante,
]


@pytest.fixture
def tablas_legacy(transactional_db):
    """Crea las tablas legacy necesarias para los tests que escriben en BD."""
    existentes = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        for modelo in MODELOS_LEGACY:
            if modelo._meta.db_table not in existentes:
                schema_editor.create_model(modelo)
    # transactional_db no hace rollback: limpia los datos del test anterior.
    # SQL crudo en orden inverso: .delete() del ORM usaría el collector y
    # consultaría tablas legacy que no existen (inscripciones, notas...).
    for modelo in reversed(MODELOS_LEGACY):
        with connection.cursor() as cursor:
            cursor.execute(f'DELETE FROM "{modelo._meta.db_table}"')  # nosec B608
    yield