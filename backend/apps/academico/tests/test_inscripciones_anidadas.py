"""
Tests para la inscripción de alumnos con representante anidado.

Valida el flujo completo en cascada:
  1. Creación exitosa (Alumno + Representante + AlumnoRepresentante + Inscripción).
  2. Idempotencia del representante por cédula (no se duplica el tutor).
  3. Rollback atómico (si falla la inscripción, no queda rastro en BD).

Todos los modelos son legacy (managed=False), por lo que las tablas se crean
manual mente en la BD de test (SQLite en memoria). El fixture tablas_legacy
(conftest) crea las tablas base; este fixture añade las faltantes con SQL
directo porque schema_editor.create_model() no las materializa reliably.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection

from apps.academico.models import Alumnos, GruposAcademicos, Inscripciones
from apps.personal.models import RepresentantesLegales, AlumnoRepresentante


# ---------------------------------------------------------------------------
# Fixture de tablas legacy necesarias para la inscripción anidada
# ---------------------------------------------------------------------------

# Tablas adicionales que faltan tras tablas_legacy (conftest):
# Usuarios, Direcciones, Profesores, RepresentantesLegales, Alumnos,
# AlumnoRepresentante.
# Nombres de db_table reales (con guión bajo) y campos mínimos necesarios.
SQL_CREATE_ADICIONALES = [
    # core (dependencias de GruposAcademicos)
    """CREATE TABLE IF NOT EXISTS turnos (
        id_turno INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_turno VARCHAR(100) NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS secciones (
        id_seccion INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_seccion VARCHAR(100) NOT NULL
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
    """CREATE TABLE IF NOT EXISTS periodos_academicos (
        id_periodo INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_periodo VARCHAR(20) NOT NULL DEFAULT '',
        nombre_periodo VARCHAR(100) NOT NULL,
        fecha_inicio DATE NOT NULL,
        fecha_fin DATE NOT NULL,
        activo INTEGER NOT NULL DEFAULT 1
    )""",
    # academico
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

MODELOS_ADICIONALES_DELETE = [
    'inscripciones',
    'grupos_academicos',
    'periodos_academicos',
    'grados_academicos',
    'niveles_educativos',
    'secciones',
    'turnos',
]


@pytest.fixture
def tablas_inscripcion(tablas_legacy, transactional_db):
    """Crea tablas adicionales sobre tablas_legacy para tests de inscripción.

    Depende de tablas_legacy (conftest) que ya crea: Usuarios, Direcciones,
    Profesores, RepresentantesLegales, Alumnos, AlumnoRepresentante.
    """
    with connection.cursor() as cursor:  # nosec B608
        cursor.execute('PRAGMA foreign_keys = OFF')
        for sql in SQL_CREATE_ADICIONALES:
            cursor.execute(sql)

        # Limpieza de datos de tests previos
        for tabla in MODELOS_ADICIONALES_DELETE:
            cursor.execute(f'DELETE FROM "{tabla}"')  # nosec B608
        cursor.execute('PRAGMA foreign_keys = ON')

    yield

    # Teardown: limpiar datos de tablas adicionales
    with connection.cursor() as cursor:  # nosec B608
        cursor.execute('PRAGMA foreign_keys = OFF')
        for tabla in MODELOS_ADICIONALES_DELETE:
            cursor.execute(f'DELETE FROM "{tabla}"')  # nosec B608
        cursor.execute('PRAGMA foreign_keys = ON')


# ---------------------------------------------------------------------------
# Helper para crear un grupo académico válido en la BD de prueba
# ---------------------------------------------------------------------------

def _crear_grupo_prueba():
    """Crea y devuelve un GruposAcademicos con sus dependencias de core."""
    from apps.core.models import (
        PeriodosAcademicos, NivelesEducativos, GradosAcademicos,
        Secciones, Turnos,
    )

    periodo = PeriodosAcademicos.objects.create(
        nombre_periodo='Periodo de Prueba',
        fecha_inicio=date.today() - timedelta(days=30),
        fecha_fin=date.today() + timedelta(days=300),
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


# ---------------------------------------------------------------------------
# Payload base para los tests
# ---------------------------------------------------------------------------

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
# Test 1: Creación exitosa en cascada
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_inscripcion_creacion_en_cascada(tablas_inscripcion):
    """Debe crear Alumno, Representante, AlumnoRepresentante e Inscripción."""
    grupo = _crear_grupo_prueba()
    data = _payload_inscripcion(id_grupo=grupo.id_grupo)

    from apps.academico.serializers import AlumnoInscripcionSerializer
    serializer = AlumnoInscripcionSerializer(data=data)
    assert serializer.is_valid(), serializer.errors  # nosec B101
    inscripcion = serializer.save()

    assert inscripcion is not None  # nosec B101
    assert inscripcion.id_inscripcion is not None  # nosec B101
    assert inscripcion.estado_inscripcion == 'Activa'  # nosec B101

    alumno = inscripcion.alumno
    assert alumno.primer_nombre == 'Juan'  # nosec B101
    assert alumno.numero_documento_identidad == '12345678'  # nosec B101

    representante = RepresentantesLegales.objects.get(cedula='V-19888777')
    assert representante.primer_nombre == 'María'  # nosec B101
    assert representante.primer_apellido == 'Pérez'  # nosec B101

    vinculo = AlumnoRepresentante.objects.get(alumno=alumno, representante=representante)
    assert vinculo.es_principal is True  # nosec B101
    assert vinculo.parentesco == 'Padre'  # nosec B101

    assert Inscripciones.objects.filter(id_inscripcion=inscripcion.id_inscripcion).exists()  # nosec B101


# ---------------------------------------------------------------------------
# Test 2: Idempotencia del representante (no se duplica por cédula)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_inscripcion_representante_idempotente(tablas_inscripcion):
    """Un segundo alumno con la misma cédula de representante no duplica al tutor."""
    grupo = _crear_grupo_prueba()

    # Primera inscripción
    data1 = _payload_inscripcion(id_grupo=grupo.id_grupo, cedula_rep='V-15151515')
    from apps.academico.serializers import AlumnoInscripcionSerializer
    serializer1 = AlumnoInscripcionSerializer(data=data1)
    assert serializer1.is_valid(), serializer1.errors  # nosec B101
    inscripcion1 = serializer1.save()

    # Segunda inscripción con mismo representante pero distinto alumno
    data2 = _payload_inscripcion(
        id_grupo=grupo.id_grupo,
        cedula_rep='V-15151515',
    )
    data2['numero_documento_identidad'] = '87654321'
    data2['cedula_escolar'] = 'CE-2026-002'
    serializer2 = AlumnoInscripcionSerializer(data=data2)
    assert serializer2.is_valid(), serializer2.errors  # nosec B101
    inscripcion2 = serializer2.save()

    # El representante debe seguir siendo uno solo
    assert RepresentantesLegales.objects.filter(cedula='V-15151515').count() == 1  # nosec B101

    # Cada alumno tiene su propio vínculo
    assert AlumnoRepresentante.objects.filter(alumno=inscripcion1.alumno).count() == 1  # nosec B101
    assert AlumnoRepresentante.objects.filter(alumno=inscripcion2.alumno).count() == 1  # nosec B101

    # Ambas inscripciones existen
    assert Inscripciones.objects.count() == 2  # nosec B101


# ---------------------------------------------------------------------------
# Test 3: Rollback atómico (falla la inscripción → no queda rastro)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_inscripcion_rollback_atomico(tablas_inscripcion):
    """Si falla la creación de la Inscripción, no debe quedar Alumno ni Representante."""
    # Usamos un id_grupo que NO existe para forzar DoesNotExist dentro del atomic()
    id_grupo_inexistente = 999999
    data = _payload_inscripcion(id_grupo=id_grupo_inexistente)

    from apps.academico.serializers import AlumnoInscripcionSerializer
    serializer = AlumnoInscripcionSerializer(data=data)
    assert serializer.is_valid(), serializer.errors  # nosec B101

    with pytest.raises(Exception):
        serializer.save()

    # Tras el rollback, no debe quedar ningún rastro
    assert Alumnos.objects.count() == 0  # nosec B101
    assert RepresentantesLegales.objects.count() == 0  # nosec B101
    assert AlumnoRepresentante.objects.count() == 0  # nosec B101
    assert Inscripciones.objects.count() == 0  # nosec B101
