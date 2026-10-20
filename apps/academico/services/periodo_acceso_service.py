"""
Servicio de gobernanza de accesos docentes por token de periodo.

Centraliza la única puerta de entrada a la carga externa de notas y
criterios (URL externa sin sesión JWT): token -> ``PeriodoCalificacion``
vigente. Las vistas externas NO replican esta lógica; consumen
``PeriodoAccesoService.resolver_y_validar_periodo`` y traducen las
excepciones de dominio a respuestas HTTP.

Reglas de negocio (fuente única de verdad):
1. Token ausente o vacío -> ``TokenInvalidoError`` (vista -> 403).
2. Token inexistente -> ``TokenInvalidoError`` (403, mensaje genérico
   que no revela si el token existe).
3. Switch administrativo apagado (``activo_manual=False``) ->
   ``PeriodoCerradoError`` (vista -> 400).
4. Fecha límite de carga vencida (``now() > fecha_limite``) ->
   ``PeriodoCerradoError`` con mensaje de calendario vencido (400).

Nota de esquema: el modelo ``PeriodoCalificacion`` no posee columnas
llamadas ``esta_abierto`` ni ``fecha_cierre``; la gobernanza se expresa
con ``activo_manual`` (switch de la UI administrativa) y ``fecha_limite``
(calendario), que son los campos que evalúa
``PeriodoCalificacion.esta_abierto()``.
"""

from __future__ import annotations

from typing import Optional

from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import PeriodoCalificacion


class TokenInvalidoError(ValidationError):
    """Token de acceso docente ausente, vacío o inexistente."""

    default_message = (
        'El token de acceso docente proporcionado es inválido o ha expirado.'
    )

    def __init__(self, message=None, **kwargs):
        super().__init__(message or self.default_message, **kwargs)


class PeriodoCerradoError(ValidationError):
    """Periodo de calificación bloqueado por switch o calendario vencido."""

    default_message = (
        'El periodo de calificación correspondiente se encuentra cerrado '
        'administrativamente.'
    )
    mensaje_fecha_vencida = (
        'El periodo de calificación correspondiente se encuentra cerrado: '
        'la fecha límite de carga de notas ha expirado.'
    )

    def __init__(self, message=None, **kwargs):
        super().__init__(message or self.default_message, **kwargs)


class PeriodoAccesoService:
    """Resolución y validación del periodo asociado a un token docente."""

    @staticmethod
    def resolver_y_validar_periodo(token: Optional[str]) -> PeriodoCalificacion:
        """
        Valida el token recibido y devuelve el ``PeriodoCalificacion``
        vigente asociado.

        Excepciones de dominio:
        - ``TokenInvalidoError``: token ausente/vacío (``.strip()``) o
          inexistente en la base de datos.
        - ``PeriodoCerradoError``: switch administrativo apagado o
          fecha límite de carga de notas vencida.

        El periodo se trae con ``.only()`` sobre los campos gobernados
        (además de ``numero_periodo``, usado por las vistas en sus
        respuestas) para evitar cargar columnas pesadas innecesarias.
        """
        token_limpio = (token or '').strip()
        if not token_limpio:
            raise TokenInvalidoError()

        try:
            periodo = (
                PeriodoCalificacion.objects
                .only(
                    'id', 'numero_periodo', 'token_acceso',
                    'activo_manual', 'fecha_limite',
                )
                .get(token_acceso=token_limpio)
            )
        except PeriodoCalificacion.DoesNotExist:
            raise TokenInvalidoError()

        # Regla 3: switch de la interfaz administrativa apagado.
        if not periodo.activo_manual:
            raise PeriodoCerradoError()

        # Regla 4: calendario de carga vencido (fecha límite expirada).
        if timezone.now() > periodo.fecha_limite:
            raise PeriodoCerradoError(PeriodoCerradoError.mensaje_fecha_vencida)

        return periodo