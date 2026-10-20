"""
Servicio de generación de reportes PDF administrativos.

Absorbe la lógica de negocio de las vistas de descarga
(``DescargaInformeDescriptivoAPIView`` y
``DescargaConstanciaProsecucionAPIView``): resolución de modelos, reglas
del Ministerio (año escolar activo y fallback histórico de la constancia),
orquestación del buffer ``io.BytesIO`` y filename sanitizado. Las vistas
solo traducen las excepciones de dominio a HTTP y sirven el
``FileResponse``.

Contrato de retorno de los generadores: ``tuple[io.BytesIO, str]``
(buffer PDF posicionado al inicio, nombre de archivo apto para la
cabecera ``Content-Disposition``).

Nota de esquema/rutas: la URL de la constancia
(``prosecucion-final-pdf/<int:alumno_id>/``) no expone ``periodo_id`` y
``ConstanciaProsecucionFinal`` no mantiene FK con ``PeriodoCalificacion``;
el parámetro existe opcional por paridad de interfaz con
``generar_informe_descriptivo`` y no interviene en la resolución (el año
escolar se deriva del periodo académico activo).
"""

from __future__ import annotations

import io
import logging
import re
from typing import Optional, Tuple

from django.core.exceptions import ValidationError

from apps.core.models import PeriodosAcademicos

from ..models import (
    Alumnos,
    ConstanciaProsecucionFinal,
    EvaluacionLapsoCriterio,
    PeriodoCalificacion,
)
from ..reports import (
    generar_pdf_constancia_prosecucion,
    generar_pdf_informe_descriptivo,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excepciones de dominio (la capa HTTP las traduce a status codes).
# ---------------------------------------------------------------------------

class ReporteError(ValidationError):
    """Error de dominio durante la preparación de un reporte (vista → 500)."""

    default_message = 'No se pudo generar el reporte PDF.'

    def __init__(self, message=None, **kwargs):
        super().__init__(message or self.default_message, **kwargs)


class AlumnoNoEncontradoError(ReporteError):
    """Alumno inexistente para el reporte solicitado (vista → 404)."""

    default_message = 'Alumno no encontrado.'


class PeriodoNoEncontradoError(ReporteError):
    """Periodo de calificación inexistente (vista → 404)."""

    default_message = 'Periodo de calificación no encontrado.'


class ConstanciaNoEncontradaError(ReporteError):
    """Sin constancia de prosecución para resolver (vista → 404)."""

    default_message = (
        'No existe constancia de prosecución final para '
        'este alumno en el año escolar actual.'
    )


class ReportesService:
    """
    Fachada de generación de PDFs administrativos (informe descriptivo
    y constancia de prosecución). Toda la resolución de modelos y las
    reglas de negocio viven aquí; las vistas solo sirven bytes.
    """

    # Extrae el año escolar "YYYY-YYYY" del nombre/código del periodo
    # académico (ej: "Año Escolar 2026-2027" -> "2026-2027").
    _RE_ANIO_ESCOLAR = r'(\d{4}-\d{4})'

    @staticmethod
    def resolver_anio_escolar_activo(
        periodo=None,
    ) -> Optional[str]:
        """
        Resuelve el año escolar activo (ej. "2026-2027") a partir del
        periodo académico vigente.

        Si no se recibe ``periodo``, toma el ``PeriodosAcademicos``
        activo más reciente (``activo=True``, ordenado por
        ``-fecha_inicio``) y aplica la expresión regular sobre
        ``nombre_periodo`` + ``codigo_periodo``. Retorna ``None`` cuando
        no hay periodo activo o el patrón no coincide (el caller decide
        el fallback).
        """
        try:
            if periodo is None:
                periodo = (
                    PeriodosAcademicos.objects
                    .filter(activo=True)
                    .order_by('-fecha_inicio')
                    .first()
                )
            if periodo is None:
                return None
            coincidencia = re.search(
                ReportesService._RE_ANIO_ESCOLAR,
                f'{periodo.nombre_periodo} {periodo.codigo_periodo}',
            )
            return coincidencia.group(1) if coincidencia else None
        except Exception:
            logger.debug('Error resolviendo el año escolar activo', exc_info=True)
            return None

    @staticmethod
    def _sanitizar_filename(nombre: str) -> str:
        """
        Sustituye todo carácter fuera de ``[A-Za-z0-9._-]`` por ``_`` para
        que el filename sea seguro dentro de ``Content-Disposition``.
        """
        return re.sub(r'[^A-Za-z0-9._-]', '_', nombre)

    @classmethod
    def generar_informe_descriptivo(
        cls,
        alumno_id: int,
        periodo_id: int,
    ) -> Tuple[io.BytesIO, str]:
        """
        Prepara el PDF del Informe Descriptivo Trimestral.

        Resuelve alumno y periodo con consultas puntuales, identifica el
        grupo del alumno a través de sus evaluaciones en el lapso
        (``select_related`` — sin N+1) y delega la maquetación en
        ``reports.generar_pdf_informe_descriptivo``.

        Excepciones de dominio:
        - ``AlumnoNoEncontradoError`` / ``PeriodoNoEncontradoError`` (404).
        - ``ReporteError`` (500) ante fallos de búsqueda o render.
        """
        try:
            alumno = Alumnos.objects.get(pk=alumno_id)
        except Alumnos.DoesNotExist:
            raise AlumnoNoEncontradoError()
        except Exception:
            logger.debug('Error buscando alumno id=%s', alumno_id, exc_info=True)
            raise ReporteError('Error al buscar el alumno.')

        try:
            periodo = PeriodoCalificacion.objects.get(pk=periodo_id)
        except PeriodoCalificacion.DoesNotExist:
            raise PeriodoNoEncontradoError()
        except Exception:
            logger.debug('Error buscando periodo id=%s', periodo_id, exc_info=True)
            raise ReporteError('Error al buscar el periodo.')

        # Grupo del alumno en el lapso: una sola consulta con JOINs.
        grupo = None
        try:
            ev = (
                EvaluacionLapsoCriterio.objects
                .filter(alumno=alumno, periodo=periodo)
                .select_related('criterio__grupo')
                .first()
            )
            if ev:
                grupo = ev.criterio.grupo
        except Exception:
            logger.debug(
                'Error obteniendo grupo del alumno %s en periodo %s',
                alumno_id, periodo_id, exc_info=True,
            )

        try:
            pdf_buffer = generar_pdf_informe_descriptivo(alumno, periodo, grupo)
        except Exception:
            logger.debug(
                'Error generando PDF informe descriptivo alumno=%s periodo=%s',
                alumno_id, periodo_id, exc_info=True,
            )
            raise ReporteError('No se pudo generar el informe PDF.')

        cedula = (
            alumno.cedula_escolar or alumno.numero_documento_identidad or alumno_id
        )
        filename = cls._sanitizar_filename(
            f'Informe_Descriptivo_{cedula}_Lapso{periodo.numero_periodo}.pdf'
        )
        return pdf_buffer, filename

    @classmethod
    def generar_constancia_prosecucion(
        cls,
        alumno_id: int,
        periodo_id: Optional[int] = None,
    ) -> Tuple[io.BytesIO, str]:
        """
        Prepara el PDF de la Constancia de Prosecución Final (boleta de Julio).

        Regla del Ministerio encapsulada:
        1. Resolver el año escolar activo desde el periodo académico en
           curso.
        2. Si hay año activo, emitir la constancia registrada para ese
           periodo escolar.
        3. Si no hay periodo académico activo determinable **o** no existe
           constancia para el periodo escolar vigente, emitir la última
           constancia del histórico (orden: ``-fecha_expedicion``, ``-id``).
        4. Si el alumno no tiene constancia alguna →
           ``ConstanciaNoEncontradaError``.

        ``periodo_id`` se acepta por paridad de interfaz; la ruta actual no
        lo expone y no interviene en la resolución (ver módulo docstring).

        Excepciones de dominio: ``AlumnoNoEncontradoError`` y
        ``ConstanciaNoEncontradaError`` (404), ``ReporteError`` (500).
        """
        del periodo_id  # Paridad de firma: sin efecto sobre el dominio.

        try:
            alumno = Alumnos.objects.get(pk=alumno_id)
        except Alumnos.DoesNotExist:
            raise AlumnoNoEncontradoError()
        except Exception:
            logger.debug(
                'Error buscando alumno para constancia: id=%s', alumno_id,
                exc_info=True,
            )
            raise ReporteError('Error al buscar el alumno.')

        anio_escolar = cls.resolver_anio_escolar_activo()

        try:
            queryset = ConstanciaProsecucionFinal.objects.filter(alumno=alumno)
            constancia = None
            if anio_escolar:
                constancia = queryset.filter(periodo_escolar=anio_escolar).first()
            if constancia is None:
                # Fallback histórico: sin periodo activo o sin registro del
                # año vigente → última constancia emitida.
                constancia = queryset.order_by('-fecha_expedicion', '-id').first()
        except Exception:
            logger.debug(
                'Error buscando constancia del alumno id=%s (año escolar %s)',
                alumno_id, anio_escolar, exc_info=True,
            )
            raise ReporteError('Error al buscar la constancia.')

        if constancia is None:
            logger.debug(
                'Constancia no encontrada: alumno id=%s año escolar=%s',
                alumno_id, anio_escolar, exc_info=True,
            )
            raise ConstanciaNoEncontradaError()

        try:
            pdf_buffer = generar_pdf_constancia_prosecucion(alumno, constancia)
        except Exception:
            logger.debug(
                'Error generando PDF de constancia alumno=%s constancia=%s',
                alumno_id, getattr(constancia, 'pk', None), exc_info=True,
            )
            raise ReporteError('No se pudo generar la constancia PDF.')

        cedula = (
            alumno.cedula_escolar or alumno.numero_documento_identidad or alumno_id
        )
        filename = cls._sanitizar_filename(f'Constancia_Prosecucion_{cedula}.pdf')
        return pdf_buffer, filename
