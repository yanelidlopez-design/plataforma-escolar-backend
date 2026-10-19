"""
Tests unitarios para el endpoint de descarga del Informe Descriptivo Trimestral (PDF).

Escenarios obligatorios cubiertos:
  1. Generación exitosa de PDF con contenido binario (200 OK + %PDF + Content-Disposition).
  2. Cabecera de adjunto (Content-Disposition con attachment y filename).
  3. Protección JWT obligatoria (401 Unauthorized sin token).
  4. Manejo de errores 404 (alumno o periodo inexistentes).

La BD de test es SQLite (config.test_settings): las tablas legacy se crean
con schema_editor igual que el conftest compartido.

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
    CriterioEvaluacion,
    EvaluacionLapsoCriterio,
    GruposAcademicos,
    PeriodoCalificacion,
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

# Modelos legacy de core necesarios para GruposAcademicos y Usuarios.
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
    GruposAcademicos,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tablas_completas(transactional_db):
    """Crea TODAS las tablas legacy necesarias (usuarios + grupos) y las
    ELIMINA al finalizar para no contaminar otros tests."""
    existentes = connection.introspection.table_names()
    creadas = []
    with connection.schema_editor() as schema_editor:
        for modelo in MODELOS_LEGACY_COMPLETOS:
            if modelo._meta.db_table not in existentes:
                schema_editor.create_model(modelo)
                creadas.append(modelo)
    yield
    # Teardown: eliminar tablas creadas para no contaminar otros tests
    # que usan SQL crudo con definiciones más permisivas (p. ej. orden NULL).
    with connection.schema_editor() as schema_editor:
        for modelo in reversed(creadas):
            if modelo._meta.db_table in connection.introspection.table_names():
                schema_editor.delete_model(modelo)

from apps.core.models import Direcciones
from apps.personal.models import Profesores


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def usuario_admin(tablas_completas):
    """Usuario administrativo para autenticación JWT (force_authenticate)."""
    return Usuarios.objects.create(
        nombre_usuario=f'admin_pdf_{uuid4().hex[:8]}',
        clave_hash='pbkdf2_sha256$260000$test$testhash',
        email=f'admin_pdf_{uuid4().hex[:8]}@test.com',
        rol='admin',
        activo=True,
    )


@pytest.fixture
def periodo_abierto():
    """Lapso de calificación vigente: fecha futura y switch encendido."""
    return PeriodoCalificacion.objects.create(
        numero_periodo=1,
        fecha_limite=timezone.now() + timedelta(days=30),
        activo_manual=True,
    )


# ---------------------------------------------------------------------------
# Helpers de datos legacy (managed=False)
# ---------------------------------------------------------------------------

def _crear_grupo(nivel_nombre, grado_nombre):
    """Crea un GruposAcademicos con todas sus dependencias de core."""
    periodo = PeriodosAcademicos.objects.create(
        codigo_periodo=f'PDF-{uuid4().hex[:10]}',
        nombre_periodo='Año Escolar 2026-2027',
        fecha_inicio=timezone.now().date() - timedelta(days=60),
        fecha_fin=timezone.now().date() + timedelta(days=300),
        activo=True,
    )
    nivel = NivelesEducativos.objects.create(nombre_nivel=nivel_nombre)
    grado = GradosAcademicos.objects.create(
        nombre_grado=grado_nombre, id_nivel=nivel, orden=1,
    )
    seccion = Secciones.objects.create(nombre_seccion='A')
    turno = Turnos.objects.create(nombre_turno='Mañana')
    return GruposAcademicos.objects.create(
        periodo=periodo,
        nivel=nivel,
        grado=grado,
        seccion=seccion,
        turno=turno,
        cupo_maximo=30,
    )


def _crear_alumno(nombre, documento, cedula_escolar):
    """Crea un Alumno con los campos obligatorios del modelo legacy."""
    return Alumnos.objects.create(
        primer_nombre=nombre,
        primer_apellido='Estudiante',
        tipo_documento_identidad='V',
        numero_documento_identidad=documento,
        cedula_escolar=cedula_escolar,
        fecha_nacimiento=timezone.now().date() - timedelta(days=2000),
        genero='Femenino',
        fecha_inscripcion_inicial=timezone.now().date(),
        estatus_general='Activo',
    )


def _crear_representante(alumno):
    """Crea un RepresentanteLegales vinculado al alumno (es_principal=True)."""
    rep = RepresentantesLegales.objects.create(
        primer_nombre='María',
        primer_apellido='Representante',
        cedula=f'V-{uuid4().hex[:8].upper()}',
        telefono_principal='04125555555',
    )
    AlumnoRepresentante.objects.create(
        alumno=alumno,
        representante=rep,
        parentesco='Madre',
        es_principal=True,
    )
    return rep


def _crear_criterio(grupo, materia, descripcion):
    """Crea un CriterioEvaluacion asociado a un grupo."""
    return CriterioEvaluacion.objects.create(
        grupo=grupo,
        materia_nombre=materia,
        descripcion_criterio=descripcion,
    )


def _url_informe(alumno_id, periodo_id):
    """URL del endpoint de descarga de PDF."""
    return reverse('descarga_informe_descriptivo',
                   kwargs={'alumno_id': alumno_id, 'periodo_id': periodo_id})


# ---------------------------------------------------------------------------
# Test 1: Generación Exitosa de PDF con Contenido Binario
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_generacion_pdf_exitoso_contenido_binario(api_client, usuario_admin, periodo_abierto, tablas_completas):
    """GET con JWT válido → 200 OK, content_type application/pdf, inicia con %PDF."""
    grupo = _crear_grupo('Educación Primaria', 'Primer Grado')
    alumno = _crear_alumno('Lucía', 'V-11111111', 'CE-2026-001')
    _crear_representante(alumno)
    criterio = _crear_criterio(grupo, 'Matemática', 'Resuelve problemas de suma y resta.')
    EvaluacionLapsoCriterio.objects.create(
        alumno=alumno,
        criterio=criterio,
        periodo=periodo_abierto,
        indicador='PL',
        sugerencias='Reforzar ejercicios de aplicación.',
    )

    api_client.force_authenticate(user=usuario_admin)
    url = _url_informe(alumno.pk, periodo_abierto.pk)
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK  # nosec B101
    assert response['Content-Type'] == 'application/pdf'  # nosec B101
    contenido = b''.join(response.streaming_content)  # nosec B101
    assert contenido[:4] == b'%PDF'  # nosec B101


# ---------------------------------------------------------------------------
# Test 2: Cabecera de Adjunto (Content-Disposition)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_cabecera_adjunto_pdf(api_client, usuario_admin, periodo_abierto, tablas_completas):
    """Content-Disposition presente con attachment y filename con cédula del alumno."""
    grupo = _crear_grupo('Educación Primaria', 'Segundo Grado')
    alumno = _crear_alumno('Pedro', 'V-22222222', 'CE-2026-002')
    _crear_representante(alumno)
    criterio = _crear_criterio(grupo, 'Lengua', 'Lee con fluidez.')
    EvaluacionLapsoCriterio.objects.create(
        alumno=alumno,
        criterio=criterio,
        periodo=periodo_abierto,
        indicador='L',
        sugerencias=None,
    )

    api_client.force_authenticate(user=usuario_admin)
    url = _url_informe(alumno.pk, periodo_abierto.pk)
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK  # nosec B101
    content_disposition = response.get('Content-Disposition', '')  # nosec B101
    assert 'attachment' in content_disposition  # nosec B101
    assert 'filename=' in content_disposition  # nosec B101
    assert 'CE-2026-002' in content_disposition  # nosec B101


# ---------------------------------------------------------------------------
# Test 3: Protección JWT Obligatoria
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_proteccion_jwt_obligatoria(api_client, periodo_abierto, tablas_completas):
    """GET sin token JWT → 401 Unauthorized."""
    grupo = _crear_grupo('Educación Primaria', 'Tercer Grado')
    alumno = _crear_alumno('Ana', 'V-33333333', 'CE-2026-003')
    _crear_representante(alumno)
    criterio = _crear_criterio(grupo, 'Matemática', 'Resuelve problemas.')
    EvaluacionLapsoCriterio.objects.create(
        alumno=alumno,
        criterio=criterio,
        periodo=periodo_abierto,
        indicador='PL',
        sugerencias=None,
    )

    url = _url_informe(alumno.pk, periodo_abierto.pk)
    response = api_client.get(url)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED  # nosec B101


# ---------------------------------------------------------------------------
# Test 4: Manejo de Errores 404
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_error_404_alumno_o_periodo_inexistente(api_client, usuario_admin, periodo_abierto, tablas_completas):
    """alumno_id o periodo_id inexistentes → 404 Not Found."""
    api_client.force_authenticate(user=usuario_admin)

    # Caso A: alumno_id inexistente
    url_alumno_inexistente = _url_informe(99999, periodo_abierto.pk)
    response_a = api_client.get(url_alumno_inexistente)
    assert response_a.status_code == status.HTTP_404_NOT_FOUND  # nosec B101
    assert response_a.data['success'] is False  # nosec B101
    assert 'Alumno no encontrado' in response_a.data['error']  # nosec B101

    # Caso B: periodo_id inexistente
    grupo = _crear_grupo('Educación Primaria', 'Sexto Grado')
    alumno = _crear_alumno('Diego', 'V-44444444', 'CE-2026-004')
    _crear_representante(alumno)

    url_periodo_inexistente = _url_informe(alumno.pk, 88888)
    response_b = api_client.get(url_periodo_inexistente)
    assert response_b.status_code == status.HTTP_404_NOT_FOUND  # nosec B101
    assert response_b.data['success'] is False  # nosec B101
    assert 'Periodo de calificación no encontrado' in response_b.data['error']  # nosec B101
