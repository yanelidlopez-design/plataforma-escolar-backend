"""
Tests unitarios exhaustivos del módulo de calificaciones en lote (Paso 4).

Escenarios obligatorios cubiertos:
  1. Carga masiva exitosa en Primaria (200 OK + desglose de filas creadas).
  2. Idempotencia del reenvío (200 OK + actualizadas=2, sin duplicados).
  3. Rollback absoluto de lote mixto (400 + ninguna nota persistida).
  4. Bloqueo pedagógico de Inicial/Preescolar con letra (400 por clean()).
  5. Bloqueo por switch manual apagado o calendario vencido (400).
  6. Protección JWT del panel administrativo (401 sin token).
  7. Borrado controlado por FK PROTECT (400 controlado, jamás 500).

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
    CalificacionLiteral,
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
    tablas con su propio SQL crudo (columnas más permisivas, p. ej.
    grados_academicos.orden NULL). Dejar la tabla estricta del modelo en la
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
def usuario_admin():
    """Usuario para la autenticación JWT del panel administrativo."""
    return Usuarios.objects.create(
        nombre_usuario='admin_calif_test',
        clave_hash='pbkdf2_sha256$260000$test$testhash',
        email='admin_calif@test.com',
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
        # codigo_periodo es UNIQUE en el modelo legacy: se genera uno por
        # creación para que los tests no colisionen entre sí.
        codigo_periodo=f'CAL-{uuid4().hex[:10]}',
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


def _url_carga(periodo):
    """URL del endpoint público con el token del lapso en query params."""
    return f"{reverse('carga_calificaciones_externa')}?token={periodo.token_acceso}"


def _payload(id_grupo, items):
    """Payload del lote de calificaciones."""
    return {'id_grupo_academico': id_grupo, 'calificaciones': items}


# ---------------------------------------------------------------------------
# Test 1: Carga masiva exitosa en Primaria (200 OK + desglose creadas)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_carga_masiva_exitosa_primaria(api_client, periodo_abierto, tablas_legacy, tablas_grupos):
    """POST con notas A-E válidas en un grupo de Primaria → 200 + creadas=2."""
    grupo = _crear_grupo('Educación Primaria', 'Primer Grado')
    alumno_1 = _crear_alumno('Lucía', 'V-11111111')
    alumno_2 = _crear_alumno('Pedro', 'V-22222222')

    response = api_client.post(
        _url_carga(periodo_abierto),
        _payload(grupo.pk, [
            {'id_alumno': alumno_1.pk, 'nota_literal': 'a'},  # minúscula → 'A'
            {'id_alumno': alumno_2.pk, 'nota_literal': 'C'},
        ]),
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK  # nosec B101
    assert response.data['success'] is True  # nosec B101
    assert response.data['creadas'] == 2  # nosec B101
    assert response.data['actualizadas'] == 0  # nosec B101
    assert response.data['total'] == 2  # nosec B101

    assert CalificacionLiteral.objects.count() == 2  # nosec B101
    nota_1 = CalificacionLiteral.objects.get(
        alumno=alumno_1, grupo=grupo, periodo=periodo_abierto,
    )
    # Normalización a mayúscula persistida en la BD.
    assert nota_1.nota_literal == 'A'  # nosec B101


# ---------------------------------------------------------------------------
# Test 2: Idempotencia y reenvío (200 + actualizadas=2, sin duplicados)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_idempotencia_reenvio_actualiza_sin_duplicar(api_client, periodo_abierto, tablas_legacy, tablas_grupos):
    """Reenvío del lote con notas modificadas → actualiza sin duplicar filas."""
    grupo = _crear_grupo('Educación Primaria', 'Segundo Grado')
    alumno_1 = _crear_alumno('María', 'V-33333333')
    alumno_2 = _crear_alumno('José', 'V-44444444')

    response_1 = api_client.post(
        _url_carga(periodo_abierto),
        _payload(grupo.pk, [
            {'id_alumno': alumno_1.pk, 'nota_literal': 'A'},
            {'id_alumno': alumno_2.pk, 'nota_literal': 'C'},
        ]),
        format='json',
    )
    assert response_1.status_code == status.HTTP_200_OK  # nosec B101
    assert response_1.data['creadas'] == 2  # nosec B101

    response_2 = api_client.post(
        _url_carga(periodo_abierto),
        _payload(grupo.pk, [
            {'id_alumno': alumno_1.pk, 'nota_literal': 'B'},
            {'id_alumno': alumno_2.pk, 'nota_literal': 'D'},
        ]),
        format='json',
    )

    assert response_2.status_code == status.HTTP_200_OK  # nosec B101
    assert response_2.data['creadas'] == 0  # nosec B101
    assert response_2.data['actualizadas'] == 2  # nosec B101

    assert CalificacionLiteral.objects.count() == 2  # nosec B101
    nota_1 = CalificacionLiteral.objects.get(
        alumno=alumno_1, grupo=grupo, periodo=periodo_abierto,
    )
    nota_2 = CalificacionLiteral.objects.get(
        alumno=alumno_2, grupo=grupo, periodo=periodo_abierto,
    )
    assert nota_1.nota_literal == 'B'  # nosec B101
    assert nota_2.nota_literal == 'D'  # nosec B101


# ---------------------------------------------------------------------------
# Test 3: Rollback absoluto de lote mixto (400 + nada persistido)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_rollback_lote_mixto_ninguna_nota_se_guarda(api_client, periodo_abierto, tablas_legacy, tablas_grupos):
    """Lote con una nota válida ('A') y otra inválida ('Z') → 400 y CERO filas."""
    grupo = _crear_grupo('Educación Primaria', 'Tercer Grado')
    alumno_1 = _crear_alumno('Ana', 'V-55555555')
    alumno_2 = _crear_alumno('Luis', 'V-66666666')

    response = api_client.post(
        _url_carga(periodo_abierto),
        _payload(grupo.pk, [
            {'id_alumno': alumno_1.pk, 'nota_literal': 'A'},  # válida: debe revertirse
            {'id_alumno': alumno_2.pk, 'nota_literal': 'Z'},  # inválida: truena clean()
        ]),
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert response.data['success'] is False  # nosec B101
    assert 'no se guardó ninguna' in response.data['error']  # nosec B101
    assert 'nota_literal' in response.data['details']  # nosec B101

    # Rollback absoluto: ni la nota válida del alumno 1 se persistió.
    assert CalificacionLiteral.objects.count() == 0  # nosec B101
    assert not CalificacionLiteral.objects.filter(alumno=alumno_1).exists()  # nosec B101


# ---------------------------------------------------------------------------
# Test 4: Bloqueo pedagógico en Inicial/Preescolar (400 por clean())
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bloqueo_pedagogico_inicial_con_nota_literal(api_client, periodo_abierto, tablas_legacy, tablas_grupos):
    """Grupo de Preescolar con letra A-E → 400 por la regla del clean()."""
    grupo = _crear_grupo('Preescolar', 'Inicial 1')
    alumno = _crear_alumno('Sofía', 'V-77777777')

    response = api_client.post(
        _url_carga(periodo_abierto),
        _payload(grupo.pk, [
            {
                'id_alumno': alumno.pk,
                'nota_literal': 'A',
                'informe_descriptivo': 'Disfruta explorando con sus compañeros.',
            },
        ]),
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert response.data['success'] is False  # nosec B101
    assert 'nota_literal' in response.data['details']  # nosec B101
    assert 'Inicial/Preescolar' in str(response.data['details']['nota_literal'])  # nosec B101

    # La regla pedagógica impidió cualquier persistencia.
    assert CalificacionLiteral.objects.count() == 0  # nosec B101


# ---------------------------------------------------------------------------
# Test 5: Bloqueo por switch manual apagado o calendario vencido (400)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bloqueo_por_switch_manual_o_calendario_vencido(
    api_client, periodo_apagado, periodo_vencido, tablas_legacy, tablas_grupos,
):
    """Con activo_manual=False o fecha_limite vencida el POST retorna 400."""
    grupo = _crear_grupo('Educación Primaria', 'Cuarto Grado')
    alumno = _crear_alumno('Carla', 'V-88888888')
    items = [{'id_alumno': alumno.pk, 'nota_literal': 'B'}]

    # Variante A: switch de la interfaz administrativa apagado.
    response_switch = api_client.post(
        _url_carga(periodo_apagado),
        _payload(grupo.pk, items),
        format='json',
    )
    assert response_switch.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert 'concluido o está cerrado' in response_switch.data['error']  # nosec B101

    # Variante B: calendario vencido (fecha_limite en el pasado).
    response_vencido = api_client.post(
        _url_carga(periodo_vencido),
        _payload(grupo.pk, items),
        format='json',
    )
    assert response_vencido.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert 'concluido o está cerrado' in response_vencido.data['error']  # nosec B101

    # En ningún caso se persistieron notas.
    assert CalificacionLiteral.objects.count() == 0  # nosec B101


# ---------------------------------------------------------------------------
# Test 6: Protección JWT del ViewSet periodos-calificacion (401)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_panel_periodos_calificacion_sin_jwt_retorna_401(api_client, periodo_abierto):
    """GET listado y PATCH detalle sin token JWT deben retornar 401."""
    url_listado = reverse('periodocalificacion-list')
    response_get = api_client.get(url_listado)

    assert response_get.status_code == status.HTTP_401_UNAUTHORIZED  # nosec B101

    url_detalle = reverse('periodocalificacion-detail', kwargs={'pk': periodo_abierto.pk})
    response_patch = api_client.patch(
        url_detalle, {'activo_manual': False}, format='json',
    )

    assert response_patch.status_code == status.HTTP_401_UNAUTHORIZED  # nosec B101
    # El periodo no fue alterado sin autenticación.
    periodo_abierto.refresh_from_db()
    assert periodo_abierto.activo_manual is True  # nosec B101


# ---------------------------------------------------------------------------
# Test 7: Borrado controlado por FK PROTECT (400 controlado, no 500)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_borrado_periodo_con_notas_bloqueado_por_fk_protect(
    api_client, usuario_admin, periodo_abierto, tablas_legacy, tablas_grupos,
):
    """DELETE de un periodo con calificaciones → 400 controlado (no 500)."""
    grupo = _crear_grupo('Educación Primaria', 'Quinto Grado')
    alumno = _crear_alumno('Diego', 'V-99999999')

    # Se registra una nota válida asociada al periodo.
    nota = CalificacionLiteral.objects.create(
        alumno=alumno, grupo=grupo, periodo=periodo_abierto, nota_literal='B',
    )
    assert nota.pk is not None  # nosec B101

    api_client.force_authenticate(user=usuario_admin)
    url_detalle = reverse('periodocalificacion-detail', kwargs={'pk': periodo_abierto.pk})
    response = api_client.delete(url_detalle)

    assert response.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert 'No se puede eliminar el periodo' in str(response.data)  # nosec B101

    # Bloqueo controlado: ni el periodo ni la nota fueron eliminados.
    assert PeriodoCalificacion.objects.filter(pk=periodo_abierto.pk).exists()  # nosec B101
    assert CalificacionLiteral.objects.filter(pk=nota.pk).exists()  # nosec B101