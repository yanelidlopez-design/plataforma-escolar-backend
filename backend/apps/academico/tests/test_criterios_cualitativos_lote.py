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
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.academico.models import (
    AprendizajeAlcanzado,
    Alumnos,
    CriterioEvaluacion,
    CriterioPeriodo,
    EvaluacionLapsoCriterio,
    GruposAcademicos,
    Inscripciones,
    PeriodoCalificacion,
)
from apps.core.models import (
    GradosAcademicos,
    NivelesEducativos,
    PeriodosAcademicos,
    Secciones,
    Turnos,
    Usuarios,
)
from apps.academico.services.periodo_acceso_service import (
    PeriodoCerradoError,
    TokenInvalidoError,
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
    Inscripciones,
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
def tabla_aprendizaje_criterio(tablas_legacy, tablas_grupos):
    """Crea/completa la tabla AprendizajeAlcanzado en SQLite para los tests de carga masiva.

    Agrega todas las columnas del modelo que falten en la tabla (no solo
    ``criterio``), porque el servicio de carga masiva escribe ``sugerencias``,
    ``indicador``, ``texto`` y ``orden`` además de ``id_criterio``.
    """
    modelo = AprendizajeAlcanzado
    columnas_existentes = {
        columna.name
        for columna in connection.introspection.get_table_description(
            connection.cursor(), modelo._meta.db_table,
        )
    }
    campos_agregados = []
    with connection.schema_editor() as schema_editor:
        for campo in modelo._meta.local_fields:
            if campo.name == 'id':
                continue  # PK auto: ya existe o la BD la gestiona
            if campo.column not in columnas_existentes:
                schema_editor.add_field(modelo, campo)
                campos_agregados.append(campo)
    yield
    # Teardown: remover los campos que agregamos (en orden inverso, best-effort)
    with connection.schema_editor() as schema_editor:
        for campo in reversed(campos_agregados):
            try:
                schema_editor.remove_field(modelo, campo)
            except Exception:
                pass


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


def _url_criterios_admin():
    return reverse('criterios_cualitativos_admin')


def _payload_criterios(id_grupo, alumnos_items):
    """Payload del lote de criterios cualitativos por sección."""
    return {'id_grupo_academico': id_grupo, 'alumnos_evaluaciones': alumnos_items}


@pytest.mark.django_db
def test_criterios_admin_se_configuran_por_seccion_y_periodo(
    api_client, periodo_abierto, tabla_aprendizaje_criterio,
):
    grupo = _crear_grupo('Educación Primaria', 'Primer Grado')
    administrador = Usuarios.objects.create(
        nombre_usuario=f'admin-{uuid4().hex[:8]}',
        email=f'{uuid4().hex[:8]}@example.com',
        rol='admin',
        activo=True,
    )
    administrador.set_password('test-password')
    administrador.save()
    api_client.force_authenticate(administrador)
    endpoint = _url_criterios_admin()

    respuesta = api_client.post(endpoint, {
        'id_periodo': periodo_abierto.pk,
        'id_grado': grupo.grado_id,
        'id_seccion': grupo.seccion_id,
        'descripcion_criterio': 'Resuelve operaciones básicas.',
    })
    assert respuesta.status_code == status.HTTP_201_CREATED
    criterio_id = respuesta.data['id']
    assert CriterioEvaluacion.objects.get(pk=criterio_id).materia_nombre == ''

    periodo_siguiente = PeriodoCalificacion.objects.create(
        numero_periodo=2,
        fecha_limite=timezone.now() + timedelta(days=60),
        activo_manual=True,
    )
    respuesta = api_client.post(endpoint, {
        'id_periodo': periodo_siguiente.pk,
        'id_grado': grupo.grado_id,
        'id_seccion': grupo.seccion_id,
        'descripcion_criterio': 'Comprende textos breves.',
    })
    assert respuesta.status_code == status.HTTP_201_CREATED

    params = {
        'id_grado': grupo.grado_id,
        'id_seccion': grupo.seccion_id,
    }
    criterios_primer_periodo = api_client.get(
        reverse('evaluaciones_cualitativas_admin'),
        {**params, 'id_periodo': periodo_abierto.pk},
    )
    criterios_segundo_periodo = api_client.get(
        reverse('evaluaciones_cualitativas_admin'),
        {**params, 'id_periodo': periodo_siguiente.pk},
    )
    assert [criterio['id'] for criterio in criterios_primer_periodo.data['criterios']] == [criterio_id]
    assert len(criterios_segundo_periodo.data['criterios']) == 1

    retirada = api_client.delete(
        f'{endpoint}?id_grado={grupo.grado_id}&id_seccion={grupo.seccion_id}'
        f'&id_periodo={periodo_abierto.pk}&id_criterio={criterio_id}'
    )
    assert retirada.status_code == status.HTTP_204_NO_CONTENT
    assert CriterioEvaluacion.objects.filter(pk=criterio_id).exists()
    assert not CriterioPeriodo.objects.filter(
        criterio_id=criterio_id,
        periodo=periodo_abierto,
    ).exists()


@pytest.mark.django_db
def test_criterio_calificado_no_se_puede_retirar_del_periodo(
    api_client, periodo_abierto, tabla_aprendizaje_criterio,
):
    grupo = _crear_grupo('Educación Primaria', 'Primer Grado')
    administrador = Usuarios.objects.create(
        nombre_usuario=f'admin-{uuid4().hex[:8]}',
        email=f'{uuid4().hex[:8]}@example.com',
        rol='admin',
        activo=True,
    )
    administrador.set_password('test-password')
    administrador.save()
    api_client.force_authenticate(administrador)
    criterio = CriterioEvaluacion.objects.create(
        grupo=grupo,
        materia_nombre='Lengua',
        descripcion_criterio='Comprende textos breves.',
    )
    CriterioPeriodo.objects.create(criterio=criterio, periodo=periodo_abierto)
    alumno = _crear_alumno('Lucía', f'V-{uuid4().hex[:8]}')
    EvaluacionLapsoCriterio.objects.create(
        alumno=alumno,
        criterio=criterio,
        periodo=periodo_abierto,
        indicador='L',
    )

    respuesta = api_client.delete(
        f'{_url_criterios_admin()}?id_periodo={periodo_abierto.pk}'
        f'&id_grado={grupo.grado_id}&id_seccion={grupo.seccion_id}'
        f'&id_criterio={criterio.pk}'
    )
    assert respuesta.status_code == status.HTTP_409_CONFLICT
    assert CriterioPeriodo.objects.filter(
        criterio=criterio,
        periodo=periodo_abierto,
    ).exists()


# ---------------------------------------------------------------------------
# Test 1: Carga de Criterios Exitosa (200 OK + desglose creadas)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_carga_criterios_exitoso(api_client, periodo_abierto, tabla_aprendizaje_criterio):
    """POST con criterios cualitativos válidos → 200 + desglose creadas=2."""
    grupo = _crear_grupo('Educación Primaria', 'Primer Grado')
    alumno_1 = _crear_alumno('Lucía', 'V-11111111')
    alumno_2 = _crear_alumno('Pedro', 'V-22222222')
    criterio_1 = _crear_criterio(grupo, 'Matemática', 'Resuelve problemas de suma y resta.')
    criterio_2 = _crear_criterio(grupo, 'Lengua', 'Lee con fluidez y comprensión.')
    Inscripciones.objects.create(
        alumno=alumno_1,
        grupo=grupo,
        fecha_inscripcion=timezone.now(),
        estado_inscripcion='Activa',
    )

    response = api_client.post(
        _url_carga(periodo_abierto),
        _payload_criterios(grupo.pk, [
            {
                'id_alumno': alumno_1.pk,
                'aprendizajes_alcanzados': [
                    {'texto': 'Resuelve sumas sencillas.', 'indicador': 'PL', 'id_criterio': criterio_1.pk, 'sugerencias': 'Reforzar ejercicios.', 'orden': 0},
                    {'texto': 'Lee textos breves.', 'indicador': 'L', 'id_criterio': criterio_2.pk, 'orden': 1},
                    {'texto': 'Explica sus estrategias.', 'indicador': 'I', 'orden': 2},
                ],
                'evaluaciones': [],
            },
            {
                'id_alumno': alumno_2.pk,
                'aprendizajes_alcanzados': [
                    {'texto': 'Resuelve sumas sencillas.', 'indicador': 'PM', 'id_criterio': criterio_1.pk, 'sugerencias': 'Practicar tablas.', 'orden': 0},
                    {'texto': 'Lee textos breves.', 'indicador': 'L', 'id_criterio': criterio_2.pk, 'orden': 1},
                ],
                'evaluaciones': [],
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
    assert eval_1.sugerencias == 'Reforzar ejercicios.'  # nosec B101
    eval_2 = EvaluacionLapsoCriterio.objects.get(
        alumno=alumno_2, criterio=criterio_1, periodo=periodo_abierto,
    )
    assert eval_2.indicador == 'PM'  # nosec B101

    aprendizajes = list(AprendizajeAlcanzado.objects.filter(
        alumno=alumno_1, periodo=periodo_abierto,
    ).order_by('orden'))
    assert len(aprendizajes) == 3  # nosec B101
    assert [item.indicador for item in aprendizajes] == ['PL', 'L', 'I']  # nosec B101
    assert [item.indicador for item in EvaluacionLapsoCriterio.objects.filter(
        alumno=alumno_1, periodo=periodo_abierto,
    ).order_by('criterio_id')] == ['PL', 'L']  # nosec B101
    assert [item.indicador for item in EvaluacionLapsoCriterio.objects.filter(
        alumno=alumno_2, periodo=periodo_abierto,
    ).order_by('criterio_id')] == ['PM', 'L']  # nosec B101

    respuesta_get = api_client.get(_url_carga(periodo_abierto), format='json')
    aprendizajes_por_alumno = {
        item['id']: item['aprendizajes_alcanzados']
        for item in respuesta_get.data['alumnos']
    }
    assert aprendizajes_por_alumno[alumno_1.pk] == [  # nosec B101
        {'texto': 'Resuelve sumas sencillas.', 'sugerencias': 'Reforzar ejercicios.', 'indicador': 'PL', 'id_criterio': criterio_1.pk, 'criterio_nombre': criterio_1.descripcion_criterio, 'orden': 0},
        {'texto': 'Lee textos breves.', 'sugerencias': None, 'indicador': 'L', 'id_criterio': criterio_2.pk, 'criterio_nombre': criterio_2.descripcion_criterio, 'orden': 1},
        {'texto': 'Explica sus estrategias.', 'sugerencias': None, 'indicador': 'I', 'id_criterio': None, 'criterio_nombre': '', 'orden': 2},
    ]


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
    assert response_switch.data['detail'] == PeriodoCerradoError.default_message  # nosec B101

    # Variante B: calendario vencido (fecha_limite en el pasado).
    response_vencido = api_client.post(
        _url_carga(periodo_vencido),
        _payload_criterios(grupo.pk, items),
        format='json',
    )
    assert response_vencido.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert response_vencido.data['detail'] == PeriodoCerradoError.mensaje_fecha_vencida  # nosec B101

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

    # Caso B: token alfanumérico inventado (no existe en MariaDB).
    url_token_invalido = f"{url_sin_token}?token=token-falso-inventado-12345"
    response_token_invalido = api_client.post(url_token_invalido, payload, format='json')
    assert response_token_invalido.status_code == status.HTTP_403_FORBIDDEN  # nosec B101

    # Mensaje genérico del servicio de gobernanza (no revela si el token existe).
    assert response_sin_token.data['detail'] == TokenInvalidoError.default_message  # nosec B101
    assert response_token_invalido.data['detail'] == TokenInvalidoError.default_message  # nosec B101

    # Ninguna evaluación se persistió por intentos fallidos de autenticación.
    assert EvaluacionLapsoCriterio.objects.count() == 0  # nosec B101


# ---------------------------------------------------------------------------
# Test 6: Lectura Pública Exitosa - GET 200 OK
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_lectura_publica_criterios_exitoso_200(api_client, periodo_abierto, tabla_aprendizaje_criterio):
    """GET con token válido y periodo abierto → 200 OK con grupo, criterios y alumnos."""
    grupo = _crear_grupo('Educación Primaria', 'Primer Grado')
    alumno = _crear_alumno('Lucía', 'V-11111111')
    criterio_1 = _crear_criterio(grupo, 'Matemática', 'Resuelve problemas de suma y resta.')
    criterio_2 = _crear_criterio(grupo, 'Lengua', 'Lee con fluidez y comprensión.')

    # Inscripción activa del alumno en el grupo.
    Inscripciones.objects.create(
        alumno=alumno,
        grupo=grupo,
        fecha_inscripcion=timezone.now(),
        estado_inscripcion='Activa',
        monto_pago=None,
        referencia_bancaria=None,
    )

    # Vincular criterio con el lapso para que el grupo sea descubierto por el GET.
    EvaluacionLapsoCriterio.objects.create(
        alumno=alumno,
        criterio=criterio_1,
        periodo=periodo_abierto,
        indicador='PL',
    )
    CriterioPeriodo.objects.create(criterio=criterio_1, periodo=periodo_abierto)
    CriterioPeriodo.objects.create(criterio=criterio_2, periodo=periodo_abierto)

    response = api_client.get(_url_carga(periodo_abierto), format='json')

    assert response.status_code == status.HTTP_200_OK  # nosec B101
    assert response.data['success'] is True  # nosec B101
    assert response.data['numero_periodo'] == periodo_abierto.numero_periodo  # nosec B101

    # Llaves exactas del payload de respuesta.
    assert set(response.data.keys()) == {'success', 'numero_periodo', 'grupo', 'criterios', 'alumnos'}  # nosec B101

    # Estructura del grupo.
    assert response.data['grupo']['id'] == grupo.id_grupo  # nosec B101
    assert response.data['grupo']['grado'] == grupo.grado.nombre_grado  # nosec B101
    assert response.data['grupo']['seccion'] == grupo.seccion.nombre_seccion  # nosec B101

    # Criterios del grupo.
    assert len(response.data['criterios']) == 2  # nosec B101
    criterio_ids = {c['id'] for c in response.data['criterios']}
    assert criterio_1.pk in criterio_ids  # nosec B101
    assert criterio_2.pk in criterio_ids  # nosec B101
    for c in response.data['criterios']:
        assert set(c.keys()) == {'id', 'materia_nombre', 'descripcion_criterio'}  # nosec B101

    # Alumnos inscritos activos.
    assert len(response.data['alumnos']) == 1  # nosec B101
    assert response.data['alumnos'][0]['id'] == alumno.id_alumno  # nosec B101
    assert response.data['alumnos'][0]['primer_nombre'] == alumno.primer_nombre  # nosec B101
    assert response.data['alumnos'][0]['primer_apellido'] == alumno.primer_apellido  # nosec B101
    assert response.data['alumnos'][0]['cedula_escolar'] == alumno.cedula_escolar  # nosec B101


# ---------------------------------------------------------------------------
# Test 7: Bloqueo por Interruptor Administrativo - GET 400 Bad Request
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bloqueo_por_interruptor_administrativo_get_400(api_client, periodo_apagado, periodo_vencido, tablas_legacy, tablas_grupos):
    """GET con periodo switch-apagado o fecha límite vencida → 400 Bad Request."""
    grupo = _crear_grupo('Educación Primaria', 'Cuarto Grado')
    alumno = _crear_alumno('Carla', 'V-88888888')
    criterio_1 = _crear_criterio(grupo, 'Matemática', 'Resuelve problemas de suma y resta.')

    EvaluacionLapsoCriterio.objects.create(
        alumno=alumno,
        criterio=criterio_1,
        periodo=periodo_apagado,
        indicador='PL',
    )

    # Variante A: switch de la interfaz administrativa apagado.
    response_switch = api_client.get(_url_carga(periodo_apagado), format='json')
    assert response_switch.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert response_switch.data['detail'] == PeriodoCerradoError.default_message  # nosec B101

    # Variante B: calendario vencido (fecha_limite en el pasado).
    EvaluacionLapsoCriterio.objects.create(
        alumno=alumno,
        criterio=criterio_1,
        periodo=periodo_vencido,
        indicador='PL',
    )
    response_vencido = api_client.get(_url_carga(periodo_vencido), format='json')
    assert response_vencido.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert response_vencido.data['detail'] == PeriodoCerradoError.mensaje_fecha_vencida  # nosec B101


# ---------------------------------------------------------------------------
# Test 8: Denegación por Token Ausente o Inválido - GET 403 Forbidden
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_denegacion_token_ausente_o_invalido_get_403(api_client, periodo_abierto, tablas_legacy, tablas_grupos):
    """GET sin token o con token inventado → 403 Forbidden genérico."""
    url_base = reverse('carga_criterios_externa')

    # Caso A: sin parámetro de token en la URL.
    response_sin_token = api_client.get(url_base, format='json')
    assert response_sin_token.status_code == status.HTTP_403_FORBIDDEN  # nosec B101
    assert response_sin_token.data['detail'] == TokenInvalidoError.default_message  # nosec B101

    # Caso B: token alfanumérico inventado (no existe en MariaDB).
    url_token_invalido = f'{url_base}?token=token-falso-inventado-12345'
    response_token_invalido = api_client.get(url_token_invalido, format='json')
    assert response_token_invalido.status_code == status.HTTP_403_FORBIDDEN  # nosec B101
    assert response_token_invalido.data['detail'] == TokenInvalidoError.default_message  # nosec B101
