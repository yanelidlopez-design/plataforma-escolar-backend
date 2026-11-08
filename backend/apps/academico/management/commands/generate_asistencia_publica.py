import logging
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import IntegrityError

from academico.models import ConfiguracionAsistenciaPublica

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Genera automáticamente ConfiguracionAsistenciaPublica de lunes a viernes con vigencia de 24 h (7:00‑7:00)'

    def handle(self, *args, **options):
        today = timezone.localdate()
        # Sólo generar de lunes (0) a viernes (4)
        if today.weekday() > 4:
            logger.info('Hoy es fin de semana; no se crea configuración de asistencia pública.')
            return

        # Evitar duplicados (campo unique en modelo)
        if ConfiguracionAsistenciaPublica.objects.filter(fecha_dia=today).exists():
            logger.info('Ya existe ConfiguracionAsistenciaPublica para %s', today)
            return

        try:
            config = ConfiguracionAsistenciaPublica(fecha_dia=today, activo=False)
            # clean() calculará vigencia_inicio/fin y validará día
            config.full_clean()
            config.save()
            logger.info('Configuración de asistencia pública creada para %s (token %s)', today, config.token_acceso)
        except IntegrityError as e:
            logger.error('Error de integridad al crear ConfiguracionAsistenciaPublica: %s', e)
        except Exception as e:
            logger.exception('Error inesperado al generar configuración de asistencia pública: %s', e)
