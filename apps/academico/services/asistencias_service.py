"""
Servicio de consulta y agregación de asistencias (SRP).

Centraliza la lógica que residía en ``AsistenciasViewSet`` y en las tres
vistas de exportación (CSV, Excel, PDF):

1. ``obtener_queryset_filtrado``: filtrado por grupo, alumno, rango de
   fechas, fecha exacta y estado, con ``select_related`` unificado (sin
   N+1). Unifica el código triplicado de las exportaciones.
2. ``calcular_estadisticas_asistencia``: agregación de presentes,
   ausentes, justificados y total en UN SOLO viaje a la BD mediante
   ``aggregate`` con ``Count`` condicional (``Q``), sustituyendo los
   4 ``.count()`` secuenciales.

Reglas de saneamiento (valores inválidos se ignoran limpiamente para no
romper la BD legacy):
    * Fechas con formato distinto a ``YYYY-MM-DD`` -> se ignoran.
    * ``grupo_id`` / ``alumno_id`` no numéricos -> se ignoran.
    * ``estado`` fuera de ``{P, A, J}`` -> se ignora.
"""

from __future__ import annotations

from datetime import datetime

from django.db.models import Count, Q, QuerySet

from ..models import Asistencias


class AsistenciasService:
    """Consultas y agregaciones de asistencias, sin lógica HTTP."""

    # Relaciones que necesitan el serializer y los reportes (sin N+1).
    _SELECT_RELATED = (
        'alumno', 'grupo', 'grupo__grado', 'grupo__seccion', 'profesor_registro',
    )

    @staticmethod
    def obtener_queryset_filtrado(
        grupo_id=None,
        alumno_id=None,
        fecha_inicio=None,
        fecha_fin=None,
        estado=None,
        fecha=None,
    ) -> QuerySet:
        """
        Construye el queryset de asistencias filtrado y precargado.

        Reemplaza el filtrado manual de ``AsistenciasViewSet.get_queryset``
        y el código triplicado de ``exportar_asistencias_csv/excel/pdf``.

        Args:
            grupo_id: PK del grupo (entero o cadena numérica).
            alumno_id: PK del alumno (entero o cadena numérica).
            fecha_inicio: Fecha mínima inclusiva ``YYYY-MM-DD``.
            fecha_fin: Fecha máxima inclusiva ``YYYY-MM-DD``.
            estado: Código de ``Asistencias.ESTADO_CHOICES`` (P, A o J).
            fecha: Fecha exacta ``YYYY-MM-DD`` (uso del listado REST).

        Returns:
            QuerySet con select_related de alumno, grupo (grado, sección)
            y profesor_registro: una sola consulta al iterar (sin N+1).
        """
        qs = Asistencias.objects.select_related(*AsistenciasService._SELECT_RELATED)

        # --- grupo / alumno (enteros; no numéricos se ignoran limpiamente) ---
        for valor, campo in ((grupo_id, 'grupo_id'), (alumno_id, 'alumno_id')):
            if not valor or not str(valor).strip().isdigit():
                continue
            qs = qs.filter(**{campo: int(valor)})

        # --- fechas (YYYY-MM-DD; formato inválido se ignora limpiamente) ---
        if fecha and AsistenciasService._fecha_valida(fecha):
            qs = qs.filter(fecha=fecha)
        if fecha_inicio and AsistenciasService._fecha_valida(fecha_inicio):
            qs = qs.filter(fecha__gte=fecha_inicio)
        if fecha_fin and AsistenciasService._fecha_valida(fecha_fin):
            qs = qs.filter(fecha__lte=fecha_fin)

        # --- estado (solo códigos válidos P / A / J) ---
        if estado:
            estado_limpio = str(estado).strip().upper()
            estados_validos = {codigo for codigo, _ in Asistencias.ESTADO_CHOICES}
            if estado_limpio in estados_validos:
                qs = qs.filter(estado=estado_limpio)

        return qs

    @staticmethod
    def calcular_estadisticas_asistencia(queryset) -> dict:
        """
        Agrega las métricas de asistencia del queryset en un solo SQL.

        Sustituye los 4 ``.count()`` secuenciales (total + 3 estados) por
        un único ``aggregate`` con ``Count`` condicional sobre MariaDB.

        Args:
            queryset: Resultado de ``obtener_queryset_filtrado`` (u otro
                queryset de ``Asistencias`` ya acotado).

        Returns:
            Dict con exactamente las claves del payload del frontend:
            ``total_dias``, ``presentes``, ``ausentes``, ``justificados``
            y ``porcentaje_asistencia`` (presentes/total * 100, 2 decimales).
        """
        agregado = queryset.aggregate(
            total=Count('id_asistencia'),
            presentes=Count('id_asistencia', filter=Q(estado='P')),
            ausentes=Count('id_asistencia', filter=Q(estado='A')),
            justificados=Count('id_asistencia', filter=Q(estado='J')),
        )

        total = agregado['total'] or 0
        presentes = agregado['presentes'] or 0
        porcentaje_asistencia = round((presentes / total) * 100, 2) if total > 0 else 0

        return {
            'total_dias': total,
            'presentes': presentes,
            'ausentes': agregado['ausentes'] or 0,
            'justificados': agregado['justificados'] or 0,
            'porcentaje_asistencia': porcentaje_asistencia,
        }

    @staticmethod
    def _fecha_valida(valor) -> bool:
        """True si ``valor`` tiene el formato ``YYYY-MM-DD``."""
        try:
            datetime.strptime(str(valor), '%Y-%m-%d')
            return True
        except (TypeError, ValueError):
            return False
