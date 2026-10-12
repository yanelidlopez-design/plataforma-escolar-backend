"""
Business logic for Google Forms webhook operations.
"""
import logging
from datetime import date
from django.db import IntegrityError
from ..models import Alumnos, GruposAcademicos, Inscripciones

logger = logging.getLogger(__name__)


def procesar_alumno_webhook(data):
    """
    Procesa y crea un alumno desde datos del webhook de Google Forms.
    Valida campos requeridos y verifica duplicados.

    Args:
        data (dict): Datos del alumno del webhook

    Returns:
        tuple: (alumno, error_message) - alumno object if successful, error message if failed
    """
    # Validar campos requeridos
    campos_requeridos = ['primer_nombre', 'primer_apellido', 'numero_documento_identidad', 'cedula_escolar', 'fecha_nacimiento']
    for campo in campos_requeridos:
        if campo not in data or not data[campo]:
            return None, f'El campo {campo} es requerido'

    # Verificar si ya existe un alumno con el mismo número de documento
    if Alumnos.objects.filter(numero_documento_identidad=data['numero_documento_identidad']).exists():
        return None, 'Ya existe un alumno con este número de documento'

    # Verificar si ya existe un alumno con la misma cédula escolar
    if data.get('cedula_escolar') and Alumnos.objects.filter(cedula_escolar=data['cedula_escolar']).exists():
        return None, 'Ya existe un alumno con esta cédula escolar'

    # Crear el alumno
    alumno_data = {
        'primer_nombre': data['primer_nombre'],
        'segundo_nombre': data.get('segundo_nombre', ''),
        'primer_apellido': data['primer_apellido'],
        'segundo_apellido': data.get('segundo_apellido', ''),
        'tipo_documento_identidad': data.get('tipo_documento_identidad', 'V'),
        'numero_documento_identidad': data['numero_documento_identidad'],
        'cedula_escolar': data['cedula_escolar'],
        'fecha_nacimiento': data['fecha_nacimiento'],
        'genero': data.get('genero', 'Masculino'),
        'lugar_nacimiento': data.get('lugar_nacimiento', ''),
        'nacionalidad': data.get('nacionalidad', 'Venezolana'),
        'grupo_sanguineo': data.get('grupo_sanguineo', 'O+'),
        'peso_kg': data.get('peso_kg'),
        'talla_cm': data.get('talla_cm'),
        'talla_camisa': data.get('talla_camisa'),
        'talla_pantalon': data.get('talla_pantalon'),
        'talla_zapato': data.get('talla_zapato'),
        'alergico_a': data.get('alergico_a'),
        'tratamiento_medico': data.get('tratamiento_medico'),
        'condicion_fisica': data.get('condicion_fisica'),
        'discapacidad': data.get('discapacidad', False),
        'tipo_discapacidad': data.get('tipo_discapacidad'),
        'fecha_inscripcion_inicial': data.get('fecha_inscripcion_inicial', date.today()),
        'estatus_general': 'Activo'
    }

    try:
        alumno = Alumnos.objects.create(**alumno_data)
        return alumno, None
    except IntegrityError as e:
        logger.error(f'Error de integridad al crear alumno: {e}')
        return None, 'Error de integridad al crear el alumno'
    except Exception as e:
        logger.exception('Error inesperado al crear alumno')
        return None, 'Error inesperado al crear el alumno'


def procesar_inscripcion_webhook(alumno, data):
    """
    Procesa y crea una inscripción para un alumno desde datos del webhook.

    Args:
        alumno: Objeto Alumno ya creado
        data (dict): Datos de la inscripción del webhook

    Returns:
        tuple: (inscripcion, error_message) - inscripcion object if successful, error message if failed
    """
    if not data.get('id_grupo'):
        return None, None  # No se solicita inscripción

    try:
        grupo = GruposAcademicos.objects.get(id_grupo=data['id_grupo'])
    except GruposAcademicos.DoesNotExist:
        return None, 'El grupo especificado no existe'

    from datetime import datetime
    inscripcion_data = {
        'alumno': alumno,
        'grupo': grupo,
        'fecha_inscripcion': data.get('fecha_inscripcion') or datetime.now(),
        'estado_inscripcion': data.get('estado_inscripcion', 'Activa'),
        'monto_pago': data.get('monto_pago'),
        'referencia_bancaria': data.get('referencia_bancaria')
    }

    try:
        inscripcion = Inscripciones.objects.create(**inscripcion_data)
        return inscripcion, None
    except IntegrityError as e:
        logger.error(f'Error de integridad al crear inscripción: {e}')
        return None, 'Error de integridad al crear la inscripción'
    except Exception as e:
        logger.exception('Error inesperado al crear inscripción')
        return None, 'Error inesperado al crear la inscripción'
