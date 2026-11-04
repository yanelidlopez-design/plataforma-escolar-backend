from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from apps.academico.models import Asistencias, GruposAcademicos, Inscripciones
from apps.academico.reports_estadistica import (
    _fechas_habiles_periodo_mensual,
    _obtener_docente_asignado,
    _rango_corte_mensual,
    generar_estadistica_mensual_pdf,
)
from rest_framework.test import APIClient


def test_periodo_mensual_va_del_26_anterior_al_25_seleccionado():
    assert _rango_corte_mensual(2026, 3) == (date(2026, 2, 26), date(2026, 3, 25))  # nosec B101
    assert _rango_corte_mensual(2026, 1) == (date(2025, 12, 26), date(2026, 1, 25))  # nosec B101

def test_fechas_habiles_incluyen_ambos_extremos_y_excluyen_domingo():
    fechas = _fechas_habiles_periodo_mensual(2026, 3)

    assert fechas[0] == date(2026, 2, 26)  # nosec B101
    assert fechas[-1] == date(2026, 3, 25)  # nosec B101
    assert all(fecha.weekday() < 6 for fecha in fechas)  # nosec B101


def test_docente_del_grupo_tiene_prioridad_sobre_docente_de_alumnos():
    docente_grupo = SimpleNamespace(primer_nombre='Docente', primer_apellido='Grupo')
    docente_alumno = SimpleNamespace(primer_nombre='Docente', primer_apellido='Alumno')
    grupo = SimpleNamespace(profesor_director=docente_grupo)
    inscripciones = [
        SimpleNamespace(alumno=SimpleNamespace(id_profesor_encargado=docente_alumno)),
    ]

    assert _obtener_docente_asignado(grupo, inscripciones) is docente_grupo  # nosec B101


def test_docente_asignado_a_todos_los_alumnos_se_usa_si_grupo_no_tiene_docente():
    docente = SimpleNamespace(primer_nombre='Docente', primer_apellido='Asignado')
    grupo = SimpleNamespace(profesor_director=None)
    inscripciones = [
        SimpleNamespace(alumno=SimpleNamespace(id_profesor_encargado=docente)),
        SimpleNamespace(alumno=SimpleNamespace(id_profesor_encargado=docente)),
    ]

    assert _obtener_docente_asignado(grupo, inscripciones) is docente  # nosec B101


def test_no_infiere_docente_si_alumnos_tienen_asignaciones_distintas():
    grupo = SimpleNamespace(profesor_director=None)
    inscripciones = [
        SimpleNamespace(
            alumno=SimpleNamespace(
                id_profesor_encargado=SimpleNamespace(primer_nombre='Docente', primer_apellido='Uno')
            )
        ),
        SimpleNamespace(
            alumno=SimpleNamespace(
                id_profesor_encargado=SimpleNamespace(primer_nombre='Docente', primer_apellido='Dos')
            )
        ),
    ]

    assert _obtener_docente_asignado(grupo, inscripciones) is None  # nosec B101


def test_generador_devuelve_pdf_mensual_valido():
    alumno = SimpleNamespace(
        primer_nombre='Ana',
        segundo_nombre=None,
        primer_apellido='González',
        segundo_apellido=None,
        fecha_nacimiento=date(2018, 5, 1),
        genero='Femenino',
        lugar_nacimiento='Calabozo',
        id_direccion_residencia=SimpleNamespace(ciudad='Calabozo', estado='Guárico'),
    )
    inscripcion = SimpleNamespace(
        alumno=alumno,
        fecha_inscripcion=datetime(2026, 3, 5, 8, 0),
        estado_inscripcion='Activa',
    )
    asistencia = SimpleNamespace(fecha=date(2026, 3, 5), alumno=alumno)
    grupo = SimpleNamespace(
        grado=SimpleNamespace(nombre_grado='Primer grado'),
        seccion=SimpleNamespace(nombre_seccion='A'),
        periodo=SimpleNamespace(nombre_periodo='2026-2027'),
        profesor_director=None,
    )
    grupo_query = Mock()
    grupo_query.get.return_value = grupo
    inscripciones_query = Mock()
    inscripciones_query.select_related.return_value = inscripciones_query
    inscripciones_query.order_by.return_value = [inscripcion]
    asistencias_query = Mock()
    asistencias_query.select_related.return_value = asistencias_query
    asistencias_query.filter.return_value = [asistencia]

    with (
        patch.object(GruposAcademicos.objects, 'select_related', return_value=grupo_query),
        patch.object(Inscripciones.objects, 'filter', return_value=inscripciones_query),
        patch.object(Asistencias.objects, 'filter', return_value=asistencias_query) as consultar_asistencias,
    ):
        respuesta = generar_estadistica_mensual_pdf(1, 2026, 3)

    assert respuesta.status_code == 200  # nosec B101
    assert respuesta.content.startswith(b'%PDF')  # nosec B101
    assert 'estadistica_mensual_1_2026_03.pdf' in respuesta['Content-Disposition']  # nosec B101
    dias_consultados = consultar_asistencias.call_args.kwargs['fecha__in']
    assert date(2026, 2, 26) in dias_consultados  # nosec B101
    assert date(2026, 3, 25) in dias_consultados  # nosec B101


def test_endpoint_mensual_requiere_autenticacion():
    respuesta = APIClient().get('/api/academico/asistencias/estadistica-mensual-pdf/')

    assert respuesta.status_code == 401  # nosec B101