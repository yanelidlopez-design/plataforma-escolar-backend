"""
Tests unitarios exhaustivos del módulo de evaluación cualitativa en lote (Paso 4).

Escenarios obligatorios cubiertos:
  1. Carga masiva exitosa de criterios cualitativos (200 OK + desglose de filas creadas).
  2. Idempotencia del reenvío (200 OK + actualizadas=N, sin duplicados).
  3. Rollback absoluto de lote mixto (400 + ninguna evaluación persistida).
  4. Bloqueo por switch manual apagado o calendario vencido (400).
  5. Denegación por token ausente o inválido (403 Forbidden).

La BD de test es SQLite (config.test_settings): las tablas legacy
(managed=False) se crean con schema_editor igual que el conftest compartido.

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
)

# Modelos legacy de core requeridos para construir GruposAcademicos en la BD
# de test, en orden de dependencia FK.
MODELOS_CORE_GRUPOS = [
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
def tablas_grupos(transactional_db):
    """Crea las tablas legacy de core/grupos y las ELIMINA al terminar.

    El drop del teardown es deliberado: otros tests del repo crean estas
    tablas con su propio SQL crudo. Dejar la tabla estricta del modelo en la
    BD compartida rompería esos tests, así que se restaura el estado.
    """
    existentes = connection.introspection.table_names()
    creadas = []
    with connection.schema_editor() as schema_editor:
        for modelo in MODELOS_CORE_GRUPOS:
            if modelo._meta.db_table not in existentes:
                schema_editor.create_model(modelo)
                creadas.append(modelo)
    yield
    with connection.schema_editor() as schema_editor:
        for modelo in reversed(creadas):
            if modelo._meta.db_table in connection.introspection.table_names():
                schema_editor.delete_model(modelo)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def periodo_abierto():
    """Lapso de calificación vigente: fecha futura y switch encendido."""
    return PeriodoCalificacion.objects.create(
        numero_periodo=1,
        fecha_limite=timezone.now() + timedelta(days=30),
        activo_manual=True,
    )


@pytest.fixture
def periodo_apagado():
    """Lapso con el switch de la interfaz administrativa apagado."""
    return PeriodoCalificacion.objects.create(
        numero_periodo=2,
        fecha_limite=timezone.now() + timedelta(days=30),
        activo_manual=False,
    )


@pytest.fixture
def periodo_vencido():
    """Lapso con fecha límite de carga ya vencida."""
    return PeriodoCalificacion.objects.create(
        numero_periodo=3,
        fecha_limite=timezone.now() - timedelta(minutes=1),
        activo_manual=True,
    )


# ---------------------------------------------------------------------------
# Helpers de datos legacy (managed=False)
# ---------------------------------------------------------------------------

def _crear_grupo(nivel_nombre, grado_nombre):
    """Crea un GruposAcademicos con todas sus dependencias de core."""
    periodo = PeriodosAcademicos.objects.create(
        codigo_periodo=f'CRIT-{uuid4().hex[:10]}',
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


def _crear_alumno(nombre, documento):
    """Crea un Alumno con los campos obligatorios del modelo legacy."""
    return Alumnos.objects.create(
        primer_nombre=nombre,
        primer_apellido='Estudiante',
        tipo_documento_identidad='V',
        numero_documento_identidad=documento,
        fecha_nacimiento=timezone.now().date() - timedelta(days=2000),
        genero='Femenino',
        fecha_inscripcion_inicial=timezone.now().date(),
        estatus_general='Activo',
    )


def _crear_criterio(grupo, materia, descripcion):
    """Crea un CriterioEvaluacion asociado a un grupo."""
    return CriterioEvaluacion.objects.create(
        grupo=grupo,
        materia_nombre=materia,
        descripcion_criterio=descripcion,
    )


def _url_carga(periodo):
    """URL del endpoint público con el token del lapso en query params."""
    return f"{reverse('carga_criterios_externa')}?token={periodo.token_acceso}"


def _payload_criterios(id_grupo, alumnos_items):
    """Payload del lote de criterios cualitativos por sección."""
    return {'id_grupo_academico': id_grupo, 'alumnos_evaluaciones': alumnos_items}


# ---------------------------------------------------------------------------
# Test 1: Carga de Criterios Exitosa (200 OK + desglose creadas)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_carga_criterios_exitoso(api_client, periodo_abierto, tablas_legacy, tablas_grupos):
    """POST con criterios cualitativos válidos → 200 + desglose creadas=2."""
    grupo = _crear_grupo('Educación Primaria', 'Primer Grado')
    alumno_1 = _crear_alumno('Lucía', 'V-11111111')
    alumno_2 = _crear_alumno('Pedro', 'V-22222222')
    criterio_1 = _crear_criterio(grupo, 'Matemática', 'Resuelve problemas de suma y resta.')
    criterio_2 = _crear_criterio(grupo, 'Lengua', 'Lee con fluidez y comprensión.')

    response = api_client.post(
        _url_carga(periodo_abierto),
        _payload_criterios(grupo.pk, [
            {
                'id_alumno': alumno_1.pk,
                'evaluaciones': [
                    {'id_criterio': criterio_1.pk, 'indicador': 'PL', 'sugerencias': 'Reforzar ejercicios de aplicación.'},
                    {'id_criterio': criterio_2.pk, 'indicador': 'L', 'sugerencias': None},
                ],
            },
            {
                'id_alumno': alumno_2.pk,
                'evaluaciones': [
                    {'id_criterio': criterio_1.pk, 'indicador': 'PM', 'sugerencias': 'Practicar tablas de multiplicar.'},
                    {'id_criterio': criterio_2.pk, 'indicador': 'L', 'sugerencias': ''},
                ],
            },
        ]),
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK  # nosec B101
    assert response.data['success'] is True  # nosec B101
    assert response.data['creadas'] == 4  # nosec B101
    assert response.data['actualizadas'] == 0  # nosec B101
    assert response.data['total'] == 2  # nosec B101

    assert EvaluacionLapsoCriterio.objects.count() == 4  # nosec B101
    eval_1 = EvaluacionLapsoCriterio.objects.get(
        alumno=alumno_1, criterio=criterio_1, periodo=periodo_abierto,
    )
    assert eval_1.indicador == 'PL'  # nosec B101
    assert eval_1.sugerencias == 'Reforzar ejercicios de aplicación.'  # nosec B101
    eval_2 = EvaluacionLapsoCriterio.objects.get(
        alumno=alumno_2, criterio=criterio_1, periodo=periodo_abierto,
    )
    assert eval_2.indicador == 'PM'  # nosec B101


# ---------------------------------------------------------------------------
# Test 2: Idempotencia y Reenvío (200 OK + actualizadas=N, sin duplicados)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_idempotencia_reenvio_criterios(api_client, periodo_abierto, tablas_legacy, tablas_grupos):
    """Reenvío del lote con indicadores modificados → actualiza sin duplicar."""
    grupo = _crear_grupo('Educación Primaria', 'Segundo Grado')
    alumno_1 = _crear_alumno('María', 'V-33333333')
    alumno_2 = _crear_alumno('José', 'V-44444444')
    criterio_1 = _crear_criterio(grupo, 'Matemática', 'Resuelve problemas de suma y resta.')

    response_1 = api_client.post(
        _url_carga(periodo_abierto),
        _payload_criterios(grupo.pk, [
            {
                'id_alumno': alumno_1.pk,
                'evaluaciones': [
                    {'id_criterio': criterio_1.pk, 'indicador': 'PL', 'sugerencias': None},
                ],
            },
            {
                'id_alumno': alumno_2.pk,
                'evaluaciones': [
                    {'id_criterio': criterio_1.pk, 'indicador': 'L', 'sugerencias': None},
                ],
            },
        ]),
        format='json',
    )
    assert response_1.status_code == status.HTTP_200_OK  # nosec B101
    assert response_1.data['creadas'] == 2  # nosec B101
    assert response_1.data['actualizadas'] == 0  # nosec B101

    response_2 = api_client.post(
        _url_carga(periodo_abierto),
        _payload_criterios(grupo.pk, [
            {
                'id_alumno': alumno_1.pk,
                'evaluaciones': [
                    {'id_criterio': criterio_1.pk, 'indicador': 'L', 'sugerencias': 'Avance notable.'},
                ],
            },
            {
                'id_alumno': alumno_2.pk,
                'evaluaciones': [
                    {'id_criterio': criterio_1.pk, 'indicador': 'PM', 'sugerencias': 'Reforzar conceptos básicos.'},
                ],
            },
        ]),
        format='json',
    )

    assert response_2.status_code == status.HTTP_200_OK  # nosec B101
    assert response_2.data['creadas'] == 0  # nosec B101
    assert response_2.data['actualizadas'] == 2  # nosec B101

    # No hay filas duplicadas: sigue siendo 2 registros totales.
    assert EvaluacionLapsoCriterio.objects.count() == 2  # nosec B101
    eval_1 = EvaluacionLapsoCriterio.objects.get(
        alumno=alumno_1, criterio=criterio_1, periodo=periodo_abierto,
    )
    assert eval_1.indicador == 'L'  # nosec B101
    assert eval_1.sugerencias == 'Avance notable.'  # nosec B101
    eval_2 = EvaluacionLapsoCriterio.objects.get(
        alumno=alumno_2, criterio=criterio_1, periodo=periodo_abierto,
    )
    assert eval_2.indicador == 'PM'  # nosec B101


# ---------------------------------------------------------------------------
# Test 3: Rollback Absoluto de Lote Mixto (400 + ninguna fila persistida)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_rollback_lote_criterios_mixto_ninguna_evaluacion_se_guarda(api_client, periodo_abierto, tablas_legacy, tablas_grupos):
    """Lote con un indicador válido ('PL') y otro inválido ('Z') → 400 y CERO filas."""
    grupo = _crear_grupo('Educación Primaria', 'Tercer Grado')
    alumno_1 = _crear_alumno('Ana', 'V-55555555')
    alumno_2 = _crear_alumno('Luis', 'V-66666666')
    criterio_1 = _crear_criterio(grupo, 'Matemática', 'Resuelve problemas de suma y resta.')

    response = api_client.post(
        _url_carga(periodo_abierto),
        _payload_criterios(grupo.pk, [
            {
                'id_alumno': alumno_1.pk,
                'evaluaciones': [
                    {'id_criterio': criterio_1.pk, 'indicador': 'PL', 'sugerencias': None},
                ],
            },
            {
                'id_alumno': alumno_2.pk,
                'evaluaciones': [
                    {'id_criterio': criterio_1.pk, 'indicador': 'Z', 'sugerencias': None},
                ],
            },
        ]),
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert response.data['success'] is False  # nosec B101
    assert response.data['error'] == 'Datos inválidos.'  # nosec B101
    assert 'Indicador inválido' in str(response.data['details'])  # nosec B101

    # Rollback absoluto: ni la evaluación válida del alumno 1 se persistió.
    assert EvaluacionLapsoCriterio.objects.count() == 0  # nosec B101
    assert not EvaluacionLapsoCriterio.objects.filter(alumno=alumno_1).exists()  # nosec B101
    assert not EvaluacionLapsoCriterio.objects.filter(alumno=alumno_2).exists()  # nosec B101


# ---------------------------------------------------------------------------
# Test 4: Bloqueo por Switch Manual o Calendario Vencido (400)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bloqueo_por_switch_o_calendario_vencido(api_client, periodo_apagado, periodo_vencido, tablas_legacy, tablas_grupos):
    """Periodo con switch apagado o fecha límite vencida → 400 en ambas variantes."""
    grupo = _crear_grupo('Educación Primaria', 'Cuarto Grado')
    alumno = _crear_alumno('Carla', 'V-88888888')
    criterio_1 = _crear_criterio(grupo, 'Matemática', 'Resuelve problemas de suma y resta.')
    items = [{
        'id_alumno': alumno.pk,
        'evaluaciones': [
            {'id_criterio': criterio_1.pk, 'indicador': 'PL', 'sugerencias': None},
        ],
    }]

    # Variante A: switch de la interfaz administrativa apagado.
    response_switch = api_client.post(
        _url_carga(periodo_apagado),
        _payload_criterios(grupo.pk, items),
        format='json',
    )
    assert response_switch.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert 'concluido o está cerrado' in response_switch.data['error']  # nosec B101

    # Variante B: calendario vencido (fecha_limite en el pasado).
    response_vencido = api_client.post(
        _url_carga(periodo_vencido),
        _payload_criterios(grupo.pk, items),
        format='json',
    )
    assert response_vencido.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert 'concluido o está cerrado' in response_vencido.data['error']  # nosec B101

    # En ningún caso se persistieron evaluaciones.
    assert EvaluacionLapsoCriterio.objects.count() == 0  # nosec B101


# ---------------------------------------------------------------------------
# Test 5: Denegación por Token Ausente o Inválido (403 Forbidden)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_denegacion_token_ausente_o_invalido(api_client, periodo_abierto, tablas_legacy, tablas_grupos):
    """POST sin token o con token inventado → 403 Forbidden genérico."""
    grupo = _crear_grupo('Educación Primaria', 'Sexto Grado')
    alumno = _crear_alumno('Diego', 'V-99999999')
    criterio_1 = _crear_criterio(grupo, 'Matemática', 'Resuelve problemas de suma y resta.')
    payload = _payload_criterios(grupo.pk, [
        {
            'id_alumno': alumno.pk,
            'evaluaciones': [
                {'id_criterio': criterio_1.pk, 'indicador': 'PL', 'sugerencias': None},
            ],
        },
    ])

    # Caso A: sin parámetro de token en la URL.
    url_sin_token = reverse('carga_criterios_externa')
    response_sin_token = api_client.post(url_sin_token, payload, format='json')
    assert response_sin_token.status_code == status.HTTP_403_FORBIDDEN  # nosec B101
    assert response_sin_token.data['success'] is False  # nosec B101

    # Caso B: token alfanumérico inventado (no existe en MariaDB).
    url_token_invalido = f"{url_sin_token}?token=token-falso-inventado-12345"
    response_token_invalido = api_client.post(url_token_invalido, payload, format='json')
    assert response_token_invalido.status_code == status.HTTP_403_FORBIDDEN  # nosec B101
    assert response_token_invalido.data['success'] is False  # nosec B101

    # Mensaje genérico (no revela si el token existe o no).
    assert 'Acceso denegado' in response_token_invalido.data['error']  # nosec B101
    assert 'Token de acceso requerido' in response_sin_token.data['error']  # nosec B101

    # Ninguna evaluación se persistió por intentos fallidos de autenticación.
    assert EvaluacionLapsoCriterio.objects.count() == 0  # nosec B101
