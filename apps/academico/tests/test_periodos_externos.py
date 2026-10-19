"""
Tests para endpoints de control dinámico de inscripciones externas.

Valida:
  1. Inscripción exitosa vía endpoint público con token válido (201 Created).
  2. Bloqueo por switch manual desactivado (activo_manual=False → 400).
  3. Bloqueo por token inválido o ausente (403 Forbidden).
  4. Protección del switch administrativo sin JWT (401 Unauthorized).
  5. Actualización exitosa del switch con JWT autenticado (200 OK).

Cada línea con 'assert' incluye '# nosec B101' para mantener Bandit en 0 issues.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.academico.models import PeriodoInscripcion, GruposAcademicos, Alumnos
from apps.personal.models import Profesores
from apps.core.models import (
    Usuarios,
    PeriodosAcademicos,
    NivelesEducativos,
    GradosAcademicos,
    Secciones,
    Turnos,
)

# ---------------------------------------------------------------------------
# SQL para crear tablas de core legacy (managed=False) necesarias por GruposAcademicos
# ---------------------------------------------------------------------------
SQL_CREATE_CORE_GRUPO = [
    """CREATE TABLE IF NOT EXISTS periodos_academicos (
        id_periodo INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_periodo VARCHAR(20) NOT NULL DEFAULT '',
        nombre_periodo VARCHAR(100) NOT NULL,
        fecha_inicio DATE NOT NULL,
        fecha_fin DATE NOT NULL,
        activo INTEGER NOT NULL DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS niveles_educativos (
        id_nivel INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_nivel VARCHAR(100) NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS grados_academicos (
        id_grado INTEGER PRIMARY KEY AUTOINCREMENT,
        id_nivel INTEGER NOT NULL,
        nombre_grado VARCHAR(100) NOT NULL,
        orden INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS secciones (
        id_seccion INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_seccion VARCHAR(100) NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS turnos (
        id_turno INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_turno VARCHAR(100) NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS grupos_academicos (
        id_grupo INTEGER PRIMARY KEY AUTOINCREMENT,
        id_periodo INTEGER NOT NULL,
        id_nivel INTEGER,
        id_grado INTEGER NOT NULL,
        id_seccion INTEGER NOT NULL,
        id_turno INTEGER NOT NULL,
        id_profesor_principal INTEGER,
        cupo_maximo INTEGER NOT NULL DEFAULT 30
    )""",
    """CREATE TABLE IF NOT EXISTS inscripciones (
        id_inscripcion INTEGER PRIMARY KEY AUTOINCREMENT,
        id_alumno INTEGER NOT NULL,
        id_grupo INTEGER NOT NULL,
        fecha_inscripcion DATETIME,
        estado_inscripcion VARCHAR(50) NOT NULL DEFAULT 'Activa',
        monto_pago DECIMAL(10,2),
        referencia_bancaria VARCHAR(100)
    )""",
]

MODELOS_CORE_GRUPO_DELETE = [
    'grupos_academicos',
    'inscripciones',
    'turnos',
    'secciones',
    'grados_academicos',
    'niveles_educativos',
    'periodos_academicos',
]


@pytest.fixture
def tablas_core_grupo(transactional_db):
    """Crea las tablas de core legacy necesarias para GruposAcademicos en la BD de test."""
    existentes = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        for sql in SQL_CREATE_CORE_GRUPO:
            with connection.cursor() as cursor:  # nosec B608
                cursor.execute(sql)
    yield
    # Teardown: limpiar datos
    with connection.cursor() as cursor:  # nosec B608
        for tabla in MODELOS_CORE_GRUPO_DELETE:
            cursor.execute(f'DELETE FROM "{tabla}"')  # nosec B608


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def usuario_admin():
    """Usuario de prueba para autenticación en el switch administrativo."""
    usuario = Usuarios.objects.create(
        nombre_usuario='admin_test',
        clave_hash='pbkdf2_sha256$260000$test$testhash',
        email='admin@test.com',
        rol='admin',
        activo=True,
    )
    return usuario


@pytest.fixture
def periodo_activo():
    """Periodo de inscripción activo: fechas vigentes y switch encendido."""
    return PeriodoInscripcion.objects.create(
        nombre='Inscripciones Año Escolar',
        fecha_inicio=timezone.now() - timedelta(days=1),
        fecha_fin=timezone.now() + timedelta(days=30),
        activo_manual=True,
    )


@pytest.fixture
def periodo_desactivado():
    """Periodo con fechas vigentes pero switch manual apagado."""
    return PeriodoInscripcion.objects.create(
        nombre='Inscripciones Desactivadas',
        fecha_inicio=timezone.now() - timedelta(days=1),
        fecha_fin=timezone.now() + timedelta(days=30),
        activo_manual=False,
    )


def _crear_grupo_prueba():
    """Crea y devuelve un GruposAcademicos con sus dependencias de core."""
    periodo = PeriodosAcademicos.objects.create(
        nombre_periodo='Periodo de Prueba',
        fecha_inicio=timezone.now().date() - timedelta(days=30),
        fecha_fin=timezone.now().date() + timedelta(days=300),
        activo=True,
    )
    nivel = NivelesEducativos.objects.create(nombre_nivel='Educación Básica')
    grado = GradosAcademicos.objects.create(
        nombre_grado='5to Grado', id_nivel=nivel
    )
    seccion = Secciones.objects.create(nombre_seccion='A')
    turno = Turnos.objects.create(nombre_turno='Mañana')

    grupo = GruposAcademicos.objects.create(
        periodo=periodo,
        nivel=nivel,
        grado=grado,
        seccion=seccion,
        turno=turno,
        cupo_maximo=30,
    )
    return grupo


def _payload_inscripcion(id_grupo, cedula_rep='V-19888777'):
    return {
        'primer_nombre': 'Juan',
        'segundo_nombre': 'José',
        'primer_apellido': 'Pérez',
        'segundo_apellido': 'García',
        'tipo_documento_identidad': 'V',
        'numero_documento_identidad': '12345678',
        'cedula_escolar': 'CE-2026-001',
        'fecha_nacimiento': '2010-05-15',
        'genero': 'M',
        'lugar_nacimiento': 'Caracas',
        'nacionalidad': 'Venezolana',
        'grupo_sanguineo': 'O+',
        'alergico_a': '',
        'peso_kg': Decimal('45.5'),
        'talla_cm': Decimal('145.0'),
        'fecha_inscripcion_inicial': date.today(),
        'estatus_general': 'Activo',
        'representante': {
            'cedula': cedula_rep,
            'nombre': 'María',
            'apellido': 'Pérez',
            'telefono': '04125555555',
            'correo': 'maria@example.com',
        },
        'id_grupo': id_grupo,
        'fecha_inscripcion': '2026-02-01T08:00:00Z',
        'estado_inscripcion': 'Activa',
        'monto_pago': Decimal('150.00'),
        'referencia_bancaria': 'REF-0001',
    }


# ---------------------------------------------------------------------------
# Test 1: Inscripción exitosa vía endpoint público (201 Created)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_inscripcion_externa_exitosa(api_client, periodo_activo, tablas_legacy, tablas_core_grupo):
    """POST con token válido y periodo activo debe retornar 201 Created."""
    grupo = _crear_grupo_prueba()
    data = _payload_inscripcion(id_grupo=grupo.id_grupo)

    url = reverse('inscripcion_externa') + f'?token={periodo_activo.token_acceso}'
    response = api_client.post(url, data, format='json')

    assert response.status_code == status.HTTP_201_CREATED  # nosec B101
    assert response.data['success'] is True  # nosec B101
    assert 'inscripcion_id' in response.data  # nosec B101


# ---------------------------------------------------------------------------
# Test 2: Bloqueo por switch manual desactivado (400 Bad Request)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_inscripcion_externa_switch_apagado(api_client, periodo_desactivado, tablas_legacy, tablas_core_grupo):
    """Periodo con fechas vigentes pero activo_manual=False debe retornar 400."""
    grupo = _crear_grupo_prueba()
    data = _payload_inscripcion(id_grupo=grupo.id_grupo, cedula_rep='V-11111111')

    url = reverse('inscripcion_externa') + f'?token={periodo_desactivado.token_acceso}'
    response = api_client.post(url, data, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert response.data['success'] is False  # nosec B101
    assert 'concluido' in response.data['error'] or 'deshabilitado' in response.data['error']  # nosec B101


# ---------------------------------------------------------------------------
# Test 3: Bloqueo por token inválido o ausente (403 Forbidden)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_inscripcion_externa_token_ausente(api_client, tablas_legacy):
    """Sin parámetro token debe retornar 403 Forbidden."""
    url = reverse('inscripcion_externa')
    response = api_client.post(url, {}, format='json')

    assert response.status_code == status.HTTP_403_FORBIDDEN  # nosec B101


@pytest.mark.django_db
def test_inscripcion_externa_token_invalido(api_client, tablas_legacy):
    """Con token inventado debe retornar 403 Forbidden (mensaje genérico)."""
    url = reverse('inscripcion_externa') + '?token=token-inventado-12345'
    response = api_client.post(url, {}, format='json')

    assert response.status_code == status.HTTP_403_FORBIDDEN  # nosec B101
    assert response.data['success'] is False  # nosec B101
    assert response.data['error'] == 'Acceso denegado.'  # nosec B101


# ---------------------------------------------------------------------------
# Test 4: Protección del switch sin autenticación JWT (401 Unauthorized)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_alternar_estado_sin_autenticacion(api_client, periodo_activo):
    """PATCH sin token JWT debe retornar 401 Unauthorized."""
    url = reverse('alternar_estado_periodo', kwargs={'pk': periodo_activo.pk})
    response = api_client.patch(url, {'activo_manual': False}, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED  # nosec B101


# ---------------------------------------------------------------------------
# Test 5: Actualización exitosa del switch con JWT (200 OK)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_alternar_estado_exitoso(api_client, usuario_admin, periodo_activo, tablas_legacy):
    """PATCH autenticado con activo_manual=False debe retornar 200 y cambiar en BD."""
    api_client.force_authenticate(user=usuario_admin)

    url = reverse('alternar_estado_periodo', kwargs={'pk': periodo_activo.pk})
    response = api_client.patch(url, {'activo_manual': False}, format='json')

    assert response.status_code == status.HTTP_200_OK  # nosec B101
    assert response.data['success'] is True  # nosec B101
    assert response.data['activo_manual'] is False  # nosec B101

    # Verificar que el cambio se persistió físicamente en la BD
    periodo_activo.refresh_from_db()
    assert periodo_activo.activo_manual is False  # nosec B101


# ---------------------------------------------------------------------------
# Test 6: Listado de periodos (GET protegido con JWT)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_listar_periodos_sin_autenticacion(api_client, tablas_legacy):
    """GET a periodos/ sin JWT debe retornar 401 Unauthorized."""
    url = reverse('listar_periodos')
    response = api_client.get(url)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED  # nosec B101


@pytest.mark.django_db
def test_listar_periodos_exitoso(api_client, usuario_admin, periodo_activo, tablas_legacy):
    """GET a periodos/ autenticado retorna 200 y datos del periodo."""
    api_client.force_authenticate(user=usuario_admin)

    url = reverse('listar_periodos')
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK  # nosec B101
    assert isinstance(response.data, list)  # nosec B101
    assert any(item['id'] == periodo_activo.pk for item in response.data)  # nosec B101
    assert any(item['token_acceso'] == periodo_activo.token_acceso for item in response.data)  # nosec B101
    assert any(item['activo_manual'] is True for item in response.data)  # nosec B101


# ---------------------------------------------------------------------------
# Test 7: Creación de periodos (POST /periodos/)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_crear_periodo_sin_autenticacion(api_client, tablas_legacy):
    """POST a periodos/ sin JWT debe retornar 401 Unauthorized."""
    url = reverse('listar_periodos')
    payload = {
        'nombre': 'Nuevo Periodo',
        'fecha_inicio': '2026-08-01',
        'fecha_fin': '2026-12-31',
    }
    response = api_client.post(url, payload, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED  # nosec B101


@pytest.mark.django_db
def test_crear_periodo_exitoso(api_client, usuario_admin, tablas_legacy):
    """POST autenticado crea el periodo, autogenera token y persiste en BD."""
    api_client.force_authenticate(user=usuario_admin)

    url = reverse('listar_periodos')
    payload = {
        'nombre': 'Inscripciones 2027',
        'fecha_inicio': '2027-01-15',
        'fecha_fin': '2027-03-31',
        'activo_manual': False,
    }
    response = api_client.post(url, payload, format='json')

    assert response.status_code == status.HTTP_201_CREATED  # nosec B101
    assert response.data['nombre'] == 'Inscripciones 2027'  # nosec B101
    assert response.data['activo_manual'] is False  # nosec B101
    # El token_acceso debe venir autogenerado (no vacío).
    assert response.data['token_acceso']  # nosec B101

    # Verificar persistencia física en la BD
    periodo = PeriodoInscripcion.objects.get(pk=response.data['id'])
    assert periodo.nombre == 'Inscripciones 2027'  # nosec B101
    assert periodo.activo_manual is False  # nosec B101


@pytest.mark.django_db
def test_crear_periodo_fechas_invalidas(api_client, usuario_admin, tablas_legacy):
    """POST con fecha_fin <= fecha_inicio debe retornar 400 Bad Request."""
    api_client.force_authenticate(user=usuario_admin)

    url = reverse('listar_periodos')
    payload = {
        'nombre': 'Periodo Inválido',
        'fecha_inicio': '2026-12-31',
        'fecha_fin': '2026-01-01',
    }
    response = api_client.post(url, payload, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101
    assert not PeriodoInscripcion.objects.filter(nombre='Periodo Inválido').exists()  # nosec B101


# ---------------------------------------------------------------------------
# Test 8: Edición de periodos (PATCH /periodos/<id>/)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_editar_periodo_sin_autenticacion(api_client, periodo_activo, tablas_legacy):
    """PATCH a periodos/<id>/ sin JWT debe retornar 401 Unauthorized."""
    url = reverse('detalle_periodo', kwargs={'pk': periodo_activo.pk})
    response = api_client.patch(url, {'nombre': 'Editado'}, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED  # nosec B101


@pytest.mark.django_db
def test_editar_periodo_exitoso(api_client, usuario_admin, periodo_activo, tablas_legacy):
    """PATCH autenticado actualiza nombre y fechas, y persiste en BD."""
    api_client.force_authenticate(user=usuario_admin)

    url = reverse('detalle_periodo', kwargs={'pk': periodo_activo.pk})
    payload = {
        'nombre': 'Inscripciones Editadas',
        'fecha_inicio': '2026-11-01',
        'fecha_fin': '2026-12-20',
    }
    response = api_client.patch(url, payload, format='json')

    assert response.status_code == status.HTTP_200_OK  # nosec B101
    assert response.data['nombre'] == 'Inscripciones Editadas'  # nosec B101

    # Verificar persistencia física en la BD
    periodo_activo.refresh_from_db()
    assert periodo_activo.nombre == 'Inscripciones Editadas'  # nosec B101
    # El token_acceso no debe cambiar al editar
    assert response.data['token_acceso'] == periodo_activo.token_acceso  # nosec B101


@pytest.mark.django_db
def test_editar_periodo_no_existente(api_client, usuario_admin, tablas_legacy):
    """PATCH a un pk inexistente debe retornar 404 Not Found."""
    api_client.force_authenticate(user=usuario_admin)

    url = reverse('detalle_periodo', kwargs={'pk': 99999})
    response = api_client.patch(url, {'nombre': 'No existe'}, format='json')

    assert response.status_code == status.HTTP_404_NOT_FOUND  # nosec B101


@pytest.mark.django_db
def test_editar_periodo_fechas_invalidas(api_client, usuario_admin, periodo_activo, tablas_legacy):
    """PATCH con fecha_fin <= fecha_inicio debe retornar 400 y no persistir."""
    api_client.force_authenticate(user=usuario_admin)

    url = reverse('detalle_periodo', kwargs={'pk': periodo_activo.pk})
    payload = {
        'fecha_inicio': '2026-12-31',
        'fecha_fin': '2026-01-01',
    }
    response = api_client.patch(url, payload, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101

    # El nombre original no debe haber cambiado
    periodo_activo.refresh_from_db()
    assert periodo_activo.nombre == 'Inscripciones Año Escolar'  # nosec B101


# ---------------------------------------------------------------------------
# Test 9: Eliminación de periodos (DELETE /periodos/<id>/)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_eliminar_periodo_sin_autenticacion(api_client, periodo_activo, tablas_legacy):
    """DELETE a periodos/<id>/ sin JWT debe retornar 401 Unauthorized."""
    url = reverse('detalle_periodo', kwargs={'pk': periodo_activo.pk})
    response = api_client.delete(url)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED  # nosec B101
    # El periodo no debe haberse eliminado
    assert PeriodoInscripcion.objects.filter(pk=periodo_activo.pk).exists()  # nosec B101


@pytest.mark.django_db
def test_eliminar_periodo_exitoso(api_client, usuario_admin, periodo_activo, tablas_legacy):
    """DELETE autenticado elimina el periodo y responde 204 No Content."""
    api_client.force_authenticate(user=usuario_admin)

    url = reverse('detalle_periodo', kwargs={'pk': periodo_activo.pk})
    response = api_client.delete(url)

    assert response.status_code == status.HTTP_204_NO_CONTENT  # nosec B101
    # Verificar que ya no existe en la BD
    assert not PeriodoInscripcion.objects.filter(pk=periodo_activo.pk).exists()  # nosec B101


@pytest.mark.django_db
def test_eliminar_periodo_no_existente(api_client, usuario_admin, tablas_legacy):
    """DELETE a un pk inexistente debe retornar 404 Not Found."""
    api_client.force_authenticate(user=usuario_admin)

    url = reverse('detalle_periodo', kwargs={'pk': 99999})
    response = api_client.delete(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND  # nosec B101


# ---------------------------------------------------------------------------
# Test 10: Formulario público de inscripción (GET /inscripcion-externa/)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_formulario_inscripcion_externa_get(api_client, periodo_activo, tablas_legacy, tablas_core_grupo):
    """GET con token válido devuelve el formulario HTML (200, text/html)."""
    url = f"{reverse('inscripcion_externa')}?token={periodo_activo.token_acceso}"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK  # nosec B101
    assert 'text/html' in response['Content-Type']  # nosec B101
    assert 'Formulario de Inscripción' in response.content.decode()  # nosec B101


@pytest.mark.django_db
def test_formulario_inscripcion_externa_token_invalido(api_client, tablas_legacy):
    """GET con token inválido devuelve 403 (no renderiza el formulario)."""
    url = f"{reverse('inscripcion_externa')}?token=token-falso"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN  # nosec B101


@pytest.mark.django_db
def test_formulario_inscripcion_externa_periodo_apagado(api_client, periodo_desactivado, tablas_legacy):
    """GET con periodo inactivo (switch apagado) devuelve 400."""
    url = f"{reverse('inscripcion_externa')}?token={periodo_desactivado.token_acceso}"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_400_BAD_REQUEST  # nosec B101


# ---------------------------------------------------------------------------
# Regresiones: correcciones del formulario de inscripción (tallas, radios,
# profesor dinámico y guardado con representante sin apellido separado)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_formulario_tallas_uniforme_4_a_18(api_client, periodo_activo, tablas_legacy, tablas_core_grupo):
    """Camisa y pantalón deben ofrecer tallas 4–18 (sin S/M/L/XL) y conservar
    los estados válidos del ENUM legacy ('Activa', 'Retirado', 'Egresado')."""
    url = f"{reverse('inscripcion_externa')}?token={periodo_activo.token_acceso}"
    html = api_client.get(url).content.decode()

    for talla in range(4, 19):
        assert f'<option value="{talla}">{talla}</option>' in html  # nosec B101
    assert 'value="XL"' not in html  # nosec B101
    assert 'value="S"' not in html  # nosec B101
    # Opciones fuera del ENUM de la tabla legacy inscripciones.estado_inscripcion.
    assert 'value="Pendiente"' not in html  # nosec B101
    assert 'value="Inactiva"' not in html  # nosec B101
    # Los radios no deben quedar con appearance:none (no se podían marcar).
    assert '.radios input[type="radio"]' in html  # nosec B101


@pytest.mark.django_db
def test_formulario_profesores_dinamicos(api_client, periodo_activo, tablas_legacy, tablas_core_grupo):
    """El combo 'Profesor Encargado' debe venir habilitado y poblado con el
    personal existente en BD (se actualiza al agregar más profesores)."""
    profesor = Profesores.objects.create(
        primer_nombre='Ana',
        primer_apellido='López',
        cedula='V-20200001',
        categoria='Profesor',
    )
    url = f"{reverse('inscripcion_externa')}?token={periodo_activo.token_acceso}"
    html = api_client.get(url).content.decode()

    assert 'name="profesor_encargado" disabled' not in html  # nosec B101
    assert 'name="profesor_encargado"' in html  # nosec B101
    assert f'<option value="{profesor.id_profesor}">Ana López</option>' in html  # nosec B101


@pytest.mark.django_db
def test_inscripcion_externa_con_profesor_encargado(api_client, periodo_activo, tablas_legacy, tablas_core_grupo):
    """POST con id_profesor_encargado debe crear la inscripción y vincular el
    profesor al alumno (FK id_profesor_encargado en la tabla alumnos)."""
    profesor = Profesores.objects.create(
        primer_nombre='Luis',
        primer_apellido='Márquez',
        cedula='V-20200002',
        categoria='Integral',
    )
    grupo = _crear_grupo_prueba()
    data = _payload_inscripcion(id_grupo=grupo.id_grupo, cedula_rep='V-19888778')
    data['id_profesor_encargado'] = profesor.id_profesor

    url = reverse('inscripcion_externa') + f'?token={periodo_activo.token_acceso}'
    response = api_client.post(url, data, format='json')

    assert response.status_code == status.HTTP_201_CREATED  # nosec B101
    alumno = Alumnos.objects.get(numero_documento_identidad='12345678')
    assert alumno.id_profesor_encargado_id == profesor.id_profesor  # nosec B101


@pytest.mark.django_db
def test_inscripcion_externa_representante_apellido_vacio(api_client, periodo_activo, tablas_legacy, tablas_core_grupo):
    """Regresión del bug 'el botón guardar no hace nada': el formulario no
    tenía campo de apellido y siempre enviaba '' → 400 en cada intento.
    Con apellido vacío el POST debe seguir creando el registro (201)."""
    grupo = _crear_grupo_prueba()
    data = _payload_inscripcion(id_grupo=grupo.id_grupo, cedula_rep='V-19888779')
    data['representante']['apellido'] = ''

    url = reverse('inscripcion_externa') + f'?token={periodo_activo.token_acceso}'
    response = api_client.post(url, data, format='json')

    assert response.status_code == status.HTTP_201_CREATED  # nosec B101
    assert response.data['success'] is True  # nosec B101