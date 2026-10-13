"""
Tareas asíncronas del módulo académico (Misión 10).
Generación de reportes pesados (Excel/PDF) en segundo plano con django-q2
(broker ORM). Cada reporte obtiene un ID; el archivo binario y su estado
se persisten en MEDIA_ROOT/exports/{reporte_id}/.
"""
import json
import logging
import os
from datetime import datetime, timezone

from django.conf import settings
from django_q.tasks import async_task

logger = logging.getLogger(__name__)

# Carpeta de almacenamiento temporal de exportaciones
EXPORTS_DIR = os.path.join(settings.MEDIA_ROOT, 'exports')

# (módulo, formato) -> nombre del archivo generado
ARCHIVOS = {
    ('alumnos', 'excel'): 'alumnos.xlsx',
    ('alumnos', 'pdf'): 'alumnos.pdf',
    ('inscripciones', 'excel'): 'inscripciones.xlsx',
    ('inscripciones', 'pdf'): 'inscripciones.pdf',
}


def _carpeta_reporte(reporte_id):
    return os.path.join(EXPORTS_DIR, reporte_id)


def _ruta_estado(reporte_id):
    return os.path.join(_carpeta_reporte(reporte_id), 'estado.json')


def _escribir_estado(reporte_id, estado):
    os.makedirs(_carpeta_reporte(reporte_id), exist_ok=True)
    with open(_ruta_estado(reporte_id), 'w', encoding='utf-8') as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=2)


def leer_estado_reporte(reporte_id):
    """Lee el estado de un reporte. Devuelve None si no existe."""
    ruta = _ruta_estado(reporte_id)
    if not reporte_id or not os.path.isfile(ruta):
        return None
    try:
        with open(ruta, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def ruta_archivo_reporte(reporte_id, reporte=None):
    """Ruta absoluta del archivo generado para un reporte (o None)."""
    reporte = reporte or leer_estado_reporte(reporte_id)
    if not reporte or reporte.get('estatus') != 'Completado':
        return None
    ruta = os.path.join(_carpeta_reporte(reporte_id), reporte.get('archivo', ''))
    return ruta if os.path.isfile(ruta) else None


def encolar_exportacion(modulo, formato, queryset):
    """
    Registra el reporte como 'Procesando' y encola la tarea en django-q2.
    Devuelve el reporte_id (str) para consultar estado/descarga.
    """
    import uuid

    reporte_id = uuid.uuid4().hex
    _escribir_estado(reporte_id, {
        'reporte_id': reporte_id,
        'estatus': 'Procesando',
        'modulo': modulo,
        'formato': formato,
        'creado_en': datetime.now(timezone.utc).isoformat(),
    })
    # El queryset de Django es serializable (pickle); la tarea lo re-ejecuta
    # contra la BD desde el worker.
    async_task(
        'apps.academico.tasks.ejecutar_exportacion',
        reporte_id, modulo, formato, queryset,
    )
    logger.info('Reporte %s encolado (%s/%s)', reporte_id, modulo, formato)
    return reporte_id


def ejecutar_exportacion(reporte_id, modulo, formato, queryset):
    """
    Tarea ejecutada por el worker de django-q2: genera el archivo binario
    con el módulo de reportes y lo guarda en MEDIA_ROOT/exports/{id}/.
    """
    from . import reports

    estado = leer_estado_reporte(reporte_id) or {}
    try:
        if formato == 'excel':
            if modulo == 'alumnos':
                response = reports.exportar_alumnos_excel(queryset)
            else:
                response = reports.exportar_inscripciones_excel(queryset)
        else:  # pdf
            if modulo == 'alumnos':
                response = reports.exportar_alumnos_pdf(queryset)
            else:
                response = reports.exportar_inscripciones_pdf(queryset, {})

        nombre_archivo = ARCHIVOS.get((modulo, formato), f'{modulo}.{formato}')
        os.makedirs(_carpeta_reporte(reporte_id), exist_ok=True)
        ruta = os.path.join(_carpeta_reporte(reporte_id), nombre_archivo)
        with open(ruta, 'wb') as fh:
            fh.write(response.content)

        _escribir_estado(reporte_id, {
            **estado,
            'estatus': 'Completado',
            'archivo': nombre_archivo,
            'tamanio_bytes': len(response.content),
            'completado_en': datetime.now(timezone.utc).isoformat(),
        })
        logger.info('Reporte %s completado (%s bytes)', reporte_id, len(response.content))
    except Exception as exc:  # noqa: BLE001 -- el estado debe registrar cualquier fallo
        logger.exception('Error generando reporte %s', reporte_id)
        _escribir_estado(reporte_id, {
            **estado,
            'estatus': 'Error',
            'detalle': str(exc),
            'completado_en': datetime.now(timezone.utc).isoformat(),
        })
