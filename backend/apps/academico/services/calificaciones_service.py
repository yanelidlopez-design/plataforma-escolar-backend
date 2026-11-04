"""
Capa de servicios pura para el módulo de calificaciones (SRP).

Extrae la lógica de negocio y las transacciones masivas previamente
incrustada en ``CargaMasivaCriteriosSerializer`` hacia una capa independiente
de la presentación (views / serializers), aplicando el Principio de
Responsabilidad Única (SRP) de SOLID.

Patrones de diseño implementados:
    - Estrategia: validaciones pedagógicas diferenciadas por nivel educativo.
    - Fábrica: resolución dinámica de la estrategia de validación.

Reglas de negocio del Ministerio de Educación de Venezuela
(Institución: E.B Creación San José - Calabozo, Guárico):
    * Nivel Inicial (Preescolar): se ocultan los indicadores literales y se
      exige un ``informe_descriptivo`` obligatorio.
    * Nivel Primaria (1ro a 6to Grado): se valida el indicador cualitativo
      estricto PL / L / PM / EP / I.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Set

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from ..models import (
    Alumnos,
    AprendizajeAlcanzado,
    CriterioEvaluacion,
    EvaluacionLapsoCriterio,
    GruposAcademicos,
    Inscripciones,
    PeriodoCalificacion,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excepción de dominio
# ---------------------------------------------------------------------------

class CalificacionesServiceError(ValidationError):
    """Excepción de dominio para errores del servicio de calificaciones.

    Hereda de ``django.core.exceptions.ValidationError`` para mantener
    compatibilidad con el manejo de errores existente en serializers y views.
    """


class GrupoSinCriteriosError(CalificacionesServiceError):
    """Ningún grupo académico tiene criterios vinculados al lapso.

    Usada por ``CalificacionesService.obtener_datos_carga_criterios``; la
    capa HTTP la traduce a ``404 Not Found`` en el GET de carga externa.
    """

    default_message = 'No hay grupos con criterios cargados para este lapso.'

    def __init__(self, message=None, **kwargs):
        super().__init__(message or self.default_message, **kwargs)


# ---------------------------------------------------------------------------
# Patrón Estrategia - Validaciones pedagógicas
# ---------------------------------------------------------------------------

class ValidadorPedagogicoABC(ABC):
    """
    Interfaz común (contrato) para las estrategias de validación pedagógica.

    Cada nivel educativo del Ministerio de Educación define sus propias reglas
    de validación para las evaluaciones cualitativas de criterios.
    """

    @abstractmethod
    def validar_evaluacion(self, datos_evaluacion: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida y normaliza una única evaluación de criterio.

        Args:
            datos_evaluacion: Diccionario con los campos crudos de la
                evaluación en formato plano (literal, informe_descriptivo).

        Returns:
            Diccionario con los campos normalizados listos para persistir.

        Raises:
            ValidationError: Si los datos no cumplen las reglas del nivel.
        """


class ValidadorEducacionInicial(ValidadorPedagogicoABC):
    """
    Estrategia de validación para Educación Inicial (Preescolar).

    Reglas pedagógicas estrictas:
        1. Está prohibido ingresar cualquier literal o letra como indicador.
        2. El campo ``informe_descriptivo`` es obligatorio.
        3. Se normaliza con ``.strip()`` y no puede quedar vacío.
    """

    def validar_evaluacion(self, datos_evaluacion: Dict[str, Any]) -> Dict[str, Any]:
        literal = datos_evaluacion.get('literal')
        if literal is not None and str(literal).strip() != '':
            raise CalificacionesServiceError(
                'Educación Inicial no admite indicadores literales. '
                'No se debe enviar el campo "literal".'
            )

        informe = (datos_evaluacion.get('informe_descriptivo') or '').strip()
        if not informe:
            raise CalificacionesServiceError(
                'El campo "informe_descriptivo" es obligatorio para '
                'Educación Inicial y no puede quedar vacío.'
            )

        # Nota de diseño: el modelo ``EvaluacionLapsoCriterio`` no posee una
        # columna ``informe_descriptivo``; por lo tanto, el informe se
        # persiste en el campo ``sugerencias`` (TextField) y el indicador
        # queda como cadena vacía para cumplir la restricción NOT NULL.
        return {
            'indicador': '',
            'sugerencias': informe,
            'informe_descriptivo': informe,
        }

class ValidadorEducacionPrimaria(ValidadorPedagogicoABC):
    """
    Estrategia de validación para Educación Primaria (1ro a 6to Grado).

    Reglas pedagógicas estrictas:
        1. El indicador debe pertenecer estrictamente a:
           ['PL', 'L', 'PM', 'EP', 'I'].
        2. Se fuerza mayúsculas con ``.upper()``.
    """

    INDICADORES_VALIDOS = ('PL', 'L', 'PM', 'EP', 'I')

    def validar_evaluacion(self, datos_evaluacion: Dict[str, Any]) -> Dict[str, Any]:
        literal = (datos_evaluacion.get('literal') or '').strip().upper()
        informe = (
            (datos_evaluacion.get('informe_descriptivo') or '').strip()
        )
        if not literal and informe:
            return {
                'indicador': '',
                'sugerencias': informe,
                'informe_descriptivo': None,
            }
        if literal not in self.INDICADORES_VALIDOS:
            raise CalificacionesServiceError(
                f'Indicador inválido "{literal}". '
                f'Use uno de: {", ".join(self.INDICADORES_VALIDOS)}.'
            )

        return {
            'indicador': literal,
            'sugerencias': informe or None,
            'informe_descriptivo': None,
        }


# ---------------------------------------------------------------------------
# Fábrica de validación pedagógica
# ---------------------------------------------------------------------------

class FabricaValidacionPedagogica:
    """
    Fábrica que resuelve dinámicamente la estrategia de validación según el
    nivel educativo recibido.

    Soporta los niveles:
        - 'INICIAL'  → Educación Inicial (Preescolar).
        - 'PRIMARIA' → Educación Primaria (1ro a 6to Grado).
    """

    _ESTRATEGIAS: Dict[str, type[ValidadorPedagogicoABC]] = {
        'INICIAL': ValidadorEducacionInicial,
        'PRIMARIA': ValidadorEducacionPrimaria,
    }

    @classmethod
    def crear(cls, nivel_educativo: str) -> ValidadorPedagogicoABC:
        """
        Devuelve la instancia del validador pedagógico correspondiente.

        Args:
            nivel_educativo: Cadena que identifica el nivel ('INICIAL' o
                'PRIMARIA'). Se normaliza internamente con
                ``.strip().upper()``.

        Returns:
            Instancia concreta de ``ValidadorPedagogicoABC``.

        Raises:
            CalificacionesServiceError: Si el nivel educativo no es soportado.
        """
        clave = (nivel_educativo or '').strip().upper()
        estrategia = cls._ESTRATEGIAS.get(clave)
        if estrategia is None:
            raise CalificacionesServiceError(
                f'Nivel educativo no soportado: "{nivel_educativo}". '
                f'Valores admitidos: {", ".join(sorted(cls._ESTRATEGIAS))}.'
            )
        return estrategia()

# ---------------------------------------------------------------------------
# Servicio central de calificaciones
# ---------------------------------------------------------------------------

class CalificacionesService:
    """
    Servicio central para el procesamiento masivo de evaluaciones de
    criterios por lapso.

    Responsabilidades (SRP):
        - Validar la existencia lógica de alumnos y criterios antes del lote.
        - Aplicar la estrategia pedagógica correspondiente por nivel.
        - Persistir de forma atómica e idempotente mediante
          ``update_or_create``.
    """

    @staticmethod
    @transaction.atomic
    def procesar_carga_masiva_criterios(
        periodo_id: int,
        nivel_educativo: str,
        lote_datos: List[Dict[str, Any]],
        aprendizajes_por_alumno: Dict[int, List[Dict[str, Any]]] | None = None,
    ) -> Dict[str, Any]:
        """
        Procesa un lote masivo de evaluaciones cualitativas de forma atómica.

        Toda la operación se ejecuta dentro de ``transaction.atomic``. Si
        cualquier fila del lote falla (integridad, alumno/criterio inexistente
        o regla de negocio pedagógica), se ejecuta rollback absoluto de todo
        el lote.

        Args:
            periodo_id: ID del ``PeriodoCalificacion`` (lapso 1, 2 o 3).
            nivel_educativo: 'INICIAL' o 'PRIMARIA'.
            lote_datos: Lista plana de diccionarios, uno por evaluación,
                con la forma::

                    [
                        {
                            "alumno_id": 31,
                            "criterio_id": 12,
                            "literal": "PL",              # Primaria: PL/L/PM/EP/I
                            "informe_descriptivo": "...",  # Inicial: obligatorio
                        },
                    ]

        Returns:
            Diccionario con el resumen del procesamiento::

                {
                    'periodo_id': int,
                    'nivel_educativo': str,
                    'alumnos_procesados': int,
                    'creadas': int,
                    'actualizadas': int,
                    'total_evaluaciones': int,
                }

        Raises:
            CalificacionesServiceError: Si el periodo no existe, el nivel es
                inválido, algún alumno/criterio no existe o una evaluación
                infringe las reglas pedagógicas.
        """
        # 1) Resolver estrategia de validación (Patrón Fábrica + Estrategia).
        validador = FabricaValidacionPedagogica.crear(nivel_educativo)

        # 2) Recuperar el período (una sola consulta, solo la PK).
        try:
            periodo = PeriodoCalificacion.objects.only('id').get(pk=periodo_id)
        except PeriodoCalificacion.DoesNotExist as exc:
            raise CalificacionesServiceError(
                f'El PeriodoCalificacion con id={periodo_id} no existe.'
            ) from exc

        # 3) Extraer IDs únicos de alumnos y criterios de todo el lote.
        ids_alumnos: Set[int] = set()
        ids_criterios: Set[int] = set()
        criterios_por_alumno: Dict[int, Set[int]] = {}
        for item in lote_datos:
            alumno_id = item.get('alumno_id')
            if alumno_id is not None:
                ids_alumnos.add(int(alumno_id))
            criterio_id = item.get('criterio_id')
            if criterio_id is not None:
                ids_criterios.add(int(criterio_id))
                criterios_por_alumno.setdefault(int(alumno_id), set()).add(int(criterio_id))
        ids_alumnos.update(int(alumno_id) for alumno_id in (aprendizajes_por_alumno or {}))

        # 4) Consultas indexadas únicas contra el problema N+1.
        #    Los resultados se cargan en sets de Python para búsquedas O(1).
        alumnos_validos: Set[int] = set(
            Alumnos.objects.filter(id_alumno__in=ids_alumnos)
            .only('id_alumno')
            .values_list('id_alumno', flat=True)
        )
        criterios_validos: Set[int] = set(
            CriterioEvaluacion.objects.filter(id__in=ids_criterios)
            .only('id')
            .values_list('id', flat=True)
        )

        # 5) Procesamiento transaccional e idempotente.
        creadas = 0
        actualizadas = 0
        total_evaluaciones = 0

        for item in lote_datos:
            alumno_id = int(item.get('alumno_id'))
            if alumno_id not in alumnos_validos:
                raise CalificacionesServiceError(
                    f'El alumno con id_alumno={alumno_id} no existe en el '
                    f'sistema.'
                )

            criterio_id = int(item.get('criterio_id'))
            if criterio_id not in criterios_validos:
                raise CalificacionesServiceError(
                    f'El criterio con id={criterio_id} no existe.'
                )

            # Aplicar estrategia pedagógica (Inicial o Primaria).
            normalizado = validador.validar_evaluacion(item)

            _, creado = EvaluacionLapsoCriterio.objects.update_or_create(
                alumno_id=alumno_id,
                criterio_id=criterio_id,
                periodo_id=periodo.id,
                defaults={
                    'indicador': normalizado['indicador'],
                    'sugerencias': normalizado['sugerencias'],
                },
            )

            if creado:
                creadas += 1
            else:
                actualizadas += 1

            total_evaluaciones += 1

        aprendizajes_actualizados = 0
        for alumno_id, aprendizajes in (aprendizajes_por_alumno or {}).items():
            alumno_id = int(alumno_id)
            if alumno_id not in alumnos_validos:
                raise CalificacionesServiceError(
                    f'El alumno con id_alumno={alumno_id} no existe en el sistema.'
                )
            evaluaciones_anteriores = EvaluacionLapsoCriterio.objects.filter(
                alumno_id=alumno_id,
                periodo_id=periodo.id,
            )
            criterios_actuales = criterios_por_alumno.get(alumno_id, set())
            if criterios_actuales:
                evaluaciones_anteriores.exclude(criterio_id__in=criterios_actuales).delete()
            else:
                evaluaciones_anteriores.delete()
            AprendizajeAlcanzado.objects.filter(
                alumno_id=alumno_id,
                periodo_id=periodo.id,
            ).delete()
            AprendizajeAlcanzado.objects.bulk_create([
                AprendizajeAlcanzado(
                    alumno_id=alumno_id,
                    periodo_id=periodo.id,
                    texto=item['texto'].strip(),
                    sugerencias=(item.get('sugerencias') or '').strip() or None,
                    indicador=item['indicador'],
                    criterio_id=item.get('id_criterio'),
                    orden=item.get('orden', orden),
                )
                for orden, item in enumerate(aprendizajes)
            ])
            aprendizajes_actualizados += 1

        logger.info(
            'Carga masiva de criterios procesada: periodo=%s, nivel=%s, '
            'creadas=%s, actualizadas=%s, total=%s',
            periodo.id,
            nivel_educativo,
            creadas,
            actualizadas,
            total_evaluaciones,
        )

        return {
            'periodo_id': periodo.id,
            'nivel_educativo': nivel_educativo,
            'alumnos_procesados': len(alumnos_validos),
            'creadas': creadas,
            'actualizadas': actualizadas,
            'total_evaluaciones': total_evaluaciones,
            'aprendizajes_actualizados': aprendizajes_actualizados,
        }

    # -------------------------------------------------------------------------
    # Lectura del GET de carga de criterios (vista externa)
    # -------------------------------------------------------------------------

    @staticmethod
    def obtener_datos_carga_criterios(periodo) -> Dict[str, Any]:
        """
        Construye el payload del GET ``carga-criterios-externa`` (SRP).

        Absorbe las consultas encadenadas que residían en
        ``CargaCriteriosDocenteExternaAPIView.get`` y las consolida en
        3 consultas SQL (antes 4, sin N+1):

        1. Grupo académico con criterios evaluados en el lapso: un solo
           JOIN ``criterioevaluacion -> evaluacionlapso`` con
           ``distinct()`` + ``select_related('grado', 'seccion', 'turno')``.
        2. Criterios del grupo: ``only`` sobre las 3 columnas que
           consume la UI.
          3. Alumnos inscritos ``estado_inscripcion='Activa'`` y sus
              aprendizajes guardados para el lapso:
           ``select_related('alumno')`` + ``only`` (1 consulta).

        Args:
            periodo: ``PeriodoCalificacion`` vigente (resuelto por
                ``PeriodoAccesoService.resolver_y_validar_periodo``).

        Returns:
            Diccionario con exactamente las claves JSON que consume el
            frontend de carga de notas: ``success``, ``numero_periodo``,
            ``grupo`` (id/grado/seccion), ``criterios`` (id/materia_nombre/
            descripcion_criterio) y ``alumnos`` (id/primer_nombre/
            primer_apellido/cedula).

        Raises:
            GrupoSinCriteriosError: si ningún grupo tiene criterios en el
                lapso (la vista responde 404 con ``success/error``).
            CalificacionesServiceError: ante un fallo inesperado al
                resolver el grupo (la vista responde 403 'Acceso denegado.').
        """
        # 1) Grupo descubierto a través de los criterios evaluados en el lapso.
        try:
            grupo = (
                GruposAcademicos.objects
                .select_related('grado', 'seccion', 'turno')
                .filter(
                    Q(criterioevaluacion__periodos_configurados__periodo=periodo)
                    | Q(criterioevaluacion__evaluacionlapso__periodo=periodo)
                )
                .distinct()
                .first()
            )
        except Exception:
            logger.debug(
                'Error identificando grupo académico para el lapso %s (criterios GET)',
                getattr(periodo, 'id', periodo), exc_info=True,
            )
            raise CalificacionesServiceError('Acceso denegado.') from None

        if grupo is None:
            raise GrupoSinCriteriosError()

        # 2) Criterios de evaluación dinámicos del grupo.
        criterios = [
            {
                'id': c.id,
                'materia_nombre': c.materia_nombre,
                'descripcion_criterio': c.descripcion_criterio,
            }
            for c in CriterioEvaluacion.objects.filter(grupo=grupo).filter(
                Q(periodos_configurados__periodo=periodo)
                | Q(evaluacionlapso__periodo=periodo)
            ).distinct().only(
                'id', 'materia_nombre', 'descripcion_criterio'
            )
        ]

        # 3) Alumnos inscritos activamente en el grupo (1 consulta, sin N+1).
        inscripciones_qs = (
            Inscripciones.objects
            .filter(grupo=grupo, estado_inscripcion='Activa')
            .select_related('alumno')
            .prefetch_related('alumno__representantes_vinculados__representante')
            .only(
                'alumno__id_alumno', 'alumno__primer_nombre',
                'alumno__primer_apellido', 'alumno__cedula_escolar',
                'alumno__fecha_nacimiento', 'alumno__numero_documento_identidad',
            )
        )
        from django.utils import timezone
        alumnos = []
        for ins in inscripciones_qs:
            alumno = ins.alumno
            # Calcular edad
            edad = None
            if alumno.fecha_nacimiento:
                today = timezone.now().date()
                birth_date = alumno.fecha_nacimiento
                edad = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

            # Obtener representante principal
            representante_principal = None
            rep_vinculado = alumno.representantes_vinculados.filter(es_principal=True).first()
            if rep_vinculado and rep_vinculado.representante:
                rep = rep_vinculado.representante
                representante_principal = f"{rep.primer_nombre} {rep.primer_apellido}".strip()

            alumnos.append({
                'id': alumno.id_alumno,
                'primer_nombre': alumno.primer_nombre,
                'primer_apellido': alumno.primer_apellido,
                'cedula_escolar': alumno.cedula_escolar,
                'numero_documento_identidad': alumno.numero_documento_identidad,
                'fecha_nacimiento': alumno.fecha_nacimiento,
                'edad': edad,
                'representante_principal': representante_principal,
            })

        aprendizajes_guardados = {}
        for registro in AprendizajeAlcanzado.objects.filter(
            periodo=periodo,
            alumno_id__in=[alumno['id'] for alumno in alumnos],
        ).select_related('criterio').only(
            'alumno_id', 'texto', 'sugerencias', 'indicador', 'orden', 'criterio_id',
            'criterio__descripcion_criterio',
        ).order_by('alumno_id', 'orden', 'id'):
            aprendizajes_guardados.setdefault(registro.alumno_id, []).append({
                'texto': registro.texto,
                'sugerencias': registro.sugerencias,
                'indicador': registro.indicador,
                'id_criterio': registro.criterio_id,
                'criterio_nombre': registro.criterio.descripcion_criterio if registro.criterio else '',
                'orden': registro.orden,
            })
        for alumno in alumnos:
            alumno['aprendizajes_alcanzados'] = aprendizajes_guardados.get(alumno['id'], [])

        return {
            'success': True,
            'numero_periodo': periodo.numero_periodo,
            'grupo': {
                'id': grupo.id_grupo,
                'grado': grupo.grado.nombre_grado,
                'seccion': grupo.seccion.nombre_seccion,
            },
            'criterios': criterios,
            'alumnos': alumnos,
        }
