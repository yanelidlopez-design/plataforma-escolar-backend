"""
Tests unitarios para el endpoint de descarga de la Constancia de Prosecución
Final (boleta oficial única de Julio) en PDF.

Escenarios obligatorios cubiertos:
  1. Generación exitosa de la constancia en PDF (200 OK + application/pdf + %PDF).
  2. Cabecera de adjunto (Content-Disposition con attachment y filename).
  3. Protección JWT obligatoria (401 Unauthorized sin token).
  4. Manejo de errores 404 (alumno inexistente o sin constancia del año activo).

La BD de test es SQLite en memoria (config.test_settings): los modelos legacy
(managed=False) se crean con schema_editor igual que el conftest compartido, y
ConstanciaProsecucionFinal (managed=True) nace de la migración 0004.

Cada línea con 'assert' incluye '# nosec B101' para mantener Bandit en 0 issues.
"""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.academico.models import (
    Alumnos,
    ConstanciaProsecucionFinal,
)
from apps.core.models import (
    GradosAcademicos,
    NivelesEducativos,
    PeriodosAcademicos,
    Secciones,
    Turnos,
    Usuarios,
    Direcciones,
)
from apps.personal.models import AlumnoRepresentante, RepresentantesLegales, Profesores

# Modelos legacy (managed=False) necesarios para Alumnos y Usuarios. La
# ConstanciaProsecucionFinal es managed=True y su tabla la crea la migración.
MODELOS_LEGACY_COMPLETOS = [
    Usuarios,
    Direcciones,
    Profesores,
    RepresentantesLegales,
    Alumnos,
    AlumnoRepresentante,
    PeriodosAcademicos,
    NivelesEducativos,
    Secciones,
    Turnos,
    GradosAcademicos,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tablas_completas(transactional_db):
    """Crea TODAS las tablas legacy necesarias y las ELIMINA al finalizar para
    no contaminar otros tests que usan SQL crudo con definiciones más permisivas."""
    existentes = connection.introspection.table_names()
    creadas = []
    with connection.schema_editor() as schema_editor:
        for modelo in MODELOS_LEGACY_COMPLETOS:
            if modelo._meta.db_table not in existentes:
                schema_editor.create_model(modelo)
                creadas.append(modelo)
    yield
    # Teardown: eliminar tablas creadas para no contaminar otros tests.
    with connection.schema_editor() as schema_editor:
        for modelo in reversed(creadas):
            if modelo._meta.db_table in connection.introspection.table_names():
                schema_editor.delete_model(modelo)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def usuario_admin(tablas_completas):
    """Usuario administrativo para autenticación JWT (force_authenticate)."""
    return Usuarios.objects.create(
        nombre_usuario=f'admin_cpf_{uuid4().hex[:8]}',
        clave_hash='pbkdf2_sha256$260000$test$testhash',
        email=f'admin_cpf_{uuid4().hex[:8]}@test.com',
        rol='admin',
        activo=True,
    )


# ---------------------------------------------------------------------------
# Helpers de datos legacy (managed=False) y del escenario de la constancia
# ---------------------------------------------------------------------------

def _crear_periodo_academico_activo():
    """Periodo académico activo que la vista usa para resolver el año escolar.

    El nombre 'Año Escolar 2026-2027' hace que el regex de la vista extraiga
    '2026-2027', el mismo formato del campo periodo_escolar de la constancia.
    """
    return PeriodosAcademicos.objects.create(
        codigo_periodo=f'CPF-{uuid4().hex[:10]}',
        nombre_periodo='Año Escolar 2026-2027',
        fecha_inicio=timezone.now().date() - timedelta(days=60),
        fecha_fin=timezone.now().date() + timedelta(days=300),
        activo=True,
    )


def _crear_alumno(nombre, documento, cedula_escolar):
    """Crea un Alumno con los campos obligatorios del modelo legacy."""
    return Alumnos.objects.create(
        primer_nombre=nombre,
        segundo_nombre='María',
        primer_apellido='Estudiante',
        segundo_apellido='Prueba',
        tipo_documento_identidad='V',
        numero_documento_identidad=documento,
        cedula_escolar=cedula_escolar,
        fecha_nacimiento=timezone.now().date() - timedelta(days=2000),
        genero='Femenino',
        lugar_nacimiento='Calabozo',
        municipio_nacimiento='Francisco de Miranda',
        entidad_federal_nacimiento='Guárico',
        fecha_inscripcion_inicial=timezone.now().date(),
        estatus_general='Activo',
    )


def _crear_constancia(alumno, periodo_escolar, literal='A', grado='Tercer Grado'):
    """Crea la ConstanciaProsecucionFinal (managed=True) del alumno."""
    return ConstanciaProsecucionFinal.objects.create(
        alumno=alumno,
        periodo_escolar=periodo_escolar,
        literal_final=literal,
        promovido_al_grado=grado,
    )


def _url_constancia(alumno_id):
    """URL del endpoint de descarga de la constancia en PDF."""
    return reverse('descarga_constancia_prosecucion', kwargs={'alumno_id': alumno_id})

# ---------------------------------------------------------------------------
# Test 1: Generación Exitosa de la Constancia en PDF
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_generacion_exitosa_constancia_pdf(api_client, usuario_admin, tablas_completas):
    """GET autenticado → 200 OK, content_type application/pdf, cabecera %PDF."""
    _crear_periodo_academico_activo()
    alumno = _crear_alumno('Lucía', 'V-55555555', 'CE-CPF-001')
    _crear_constancia(alumno, '2026-2027', literal='A', grado='Tercer Grado')

    api_client.force_authenticate(user=usuario_admin)
    response = api_client.get(_url_constancia(alumno.pk))

    assert response.status_code == status.HTTP_200_OK  # nosec B101
    assert response['Content-Type'] == 'application/pdf'  # nosec B101
    contenido = b''.join(response.streaming_content)  # nosec B101
    assert contenido[:4] == b'%PDF'  # nosec B101


# ---------------------------------------------------------------------------
# Test 2: Verificación de la Cabecera de Adjunto (Content-Disposition)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_cabecera_adjunto_constancia_pdf(api_client, usuario_admin, tablas_completas):
    """Content-Disposition presente con attachment y filename con cédula."""
    _crear_periodo_academico_activo()
    alumno = _crear_alumno('Pedro', 'V-66666666', 'CE-CPF-002')
    _crear_constancia(alumno, '2026-2027', literal='B', grado='Cuarto Grado')

    api_client.force_authenticate(user=usuario_admin)
    response = api_client.get(_url_constancia(alumno.pk))

    assert response.status_code == status.HTTP_200_OK  # nosec B101
    content_disposition = response.get('Content-Disposition', '')  # nosec B101
    assert 'attachment' in content_disposition  # nosec B101
    assert 'filename=' in content_disposition  # nosec B101
    assert 'Constancia_Prosecucion_' in content_disposition  # nosec B101
    assert 'CE-CPF-002' in content_disposition  # nosec B101


# ---------------------------------------------------------------------------
# Test 3: Protección JWT Obligatoria
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_proteccion_jwt_obligatoria(api_client, tablas_completas):
    """GET sin token JWT → 401 Unauthorized."""
    _crear_periodo_academico_activo()
    alumno = _crear_alumno('Ana', 'V-77777777', 'CE-CPF-003')
    _crear_constancia(alumno, '2026-2027', literal='A', grado='Tercer Grado')

    # Sin force_authenticate: la petición viaja sin credenciales JWT.
    response = api_client.get(_url_constancia(alumno.pk))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED  # nosec B101


# ---------------------------------------------------------------------------
# Test 4: Manejo de Errores 404
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_error_404_alumno_o_constancia_inexistente(api_client, usuario_admin, tablas_completas):
    """alumno_id inexistente o alumno sin constancia del año activo → 404."""
    _crear_periodo_academico_activo()

    api_client.force_authenticate(user=usuario_admin)

    # Caso A: alumno_id inexistente.
    response_a = api_client.get(_url_constancia(99999))
    assert response_a.status_code == status.HTTP_404_NOT_FOUND  # nosec B101
    assert response_a.data['success'] is False  # nosec B101
    assert 'Alumno no encontrado' in response_a.data['error']  # nosec B101

    # Caso B: alumno existe pero no tiene constancia registrada para el año activo.
    alumno_sin_constancia = _crear_alumno('Diego', 'V-88888888', 'CE-CPF-004')
    response_b = api_client.get(_url_constancia(alumno_sin_constancia.pk))
    assert response_b.status_code == status.HTTP_404_NOT_FOUND  # nosec B101
    assert response_b.data['success'] is False  # nosec B101
    assert 'constancia' in response_b.data['error'].lower()  # nosec B101