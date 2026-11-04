"""
Business logic for Google Forms webhook operations.
"""
import logging
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction

from apps.core.models import Direcciones
from apps.personal.models import AlumnoRepresentante, Profesores, RepresentantesLegales

from ..models import Alumnos, GruposAcademicos, Inscripciones

logger = logging.getLogger(__name__)


def _a_booleano(valor, por_defecto=False):
    """
    Normaliza valores típicos de formularios ('Sí', 'No', 1, 0, 'true'...)
    a booleano real para el modelo.
    """
    if valor is None or valor == '':
        return por_defecto
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return bool(valor)
    texto = str(valor).strip().lower()
    if texto in ('sí', 'si', 's', 'true', 'verdadero', '1'):
        return True
    if texto in ('no', 'n', 'false', 'falso', '0'):
        return False
    return por_defecto


def _a_decimal(valor):
    """Convierte '15500.75' o '15.500,75' a Decimal; vacío/inválido → None."""
    if valor is None or valor == '':
        return None
    if isinstance(valor, Decimal):
        return valor
    texto = str(valor).strip().replace(' ', '')
    if ',' in texto and '.' in texto:
        texto = texto.replace('.', '').replace(',', '.')  # formato latino
    else:
        texto = texto.replace(',', '.')
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return None


def _a_entero(valor):
    """Convierte '3' o 3.0 a int; vacío/inválido → None."""
    if valor is None or valor == '':
        return None
    try:
        return int(float(valor))
    except (ValueError, TypeError):
        return None


def _a_fecha(valor):
    """Acepta ISO (yyyy-mm-dd) o dd/mm/yyyy y devuelve date; inválido → None."""
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    for formato in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def _normalizar_nombre(texto):
    """'María José  López' → 'maria jose lopez' (sin acentos, minúsculas, espacios simples)."""
    texto = unicodedata.normalize('NFD', str(texto or ''))
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return ' '.join(texto.lower().split())


def _resolver_profesor_encargado(valor):
    """
    Resuelve el profesor encargado (Docente Guía) a partir de la cédula o del
    nombre completo enviado en el webhook (campo 'profesor_encargado').
    Si no se encuentra, devuelve None y registra un warning (no bloquea
    la creación del alumno).
    """
    if valor is None or str(valor).strip() == '':
        return None
    texto = str(valor).strip()

    # 1) Por cédula: exacta o reducida a dígitos ('V-30999888' → '30999888')
    profesor = Profesores.objects.filter(cedula=texto).first()
    if profesor:
        return profesor
    digitos = ''.join(c for c in texto if c.isdigit())
    if digitos and digitos != texto:
        profesor = Profesores.objects.filter(cedula=digitos).first()
        if profesor:
            return profesor

    # 2) Por nombre completo (normalizado: sin acentos ni dobles espacios)
    objetivo = _normalizar_nombre(texto)
    if len(objetivo.split()) >= 2:
        for candidato in Profesores.objects.all():
            nombre_bd = _normalizar_nombre(
                f'{candidato.primer_nombre} {candidato.segundo_nombre or ""} '
                f'{candidato.primer_apellido} {candidato.segundo_apellido or ""}'
            )
            if nombre_bd == objetivo or nombre_bd.replace(' ', '') == objetivo.replace(' ', ''):
                return candidato

    logger.warning('Profesor encargado no encontrado en personal.Profesores: %r', valor)
    return None


def _vincular_representante_webhook(alumno, representante_data, parentesco):
    """
    Crea/busca el representante legal por cédula y lo vincula al alumno
    (misma semántica que AlumnosSerializer._vincular_representante):
    - get_or_create por cédula (reutiliza si ya existe).
    - El nombre completo se expande a primer_nombre/primer_apellido (NOT NULL legacy).
    - Se crea/actualiza la fila pivote con parentesco y es_principal=True.
    - Solo puede haber UN representante principal por alumno.
    NOTA: la pivote tiene PK compuesta (id_alumno, id_representante) en la BD,
    por eso se usa filter().update()/create() en lugar de update_or_create().
    """
    partes = str(representante_data['nombre']).split()
    primer_nombre = partes[0]
    primer_apellido = ' '.join(partes[1:]) if len(partes) > 1 else 'S/I'

    representante, _creado = RepresentantesLegales.objects.get_or_create(
        cedula=representante_data['cedula'],
        defaults={
            'primer_nombre': primer_nombre,
            'primer_apellido': primer_apellido,
            'telefono_principal': representante_data['telefono'],
            'email': representante_data.get('email') or None,
            'carnet_patria': representante_data.get('carnet_patria') or None,
            'telefono_secundario': representante_data.get('telefono_secundario') or None,
            'ocupacion': representante_data.get('ocupacion') or None,
        },
    )

    valores = {
        'parentesco': parentesco or 'Sin especificar',
        'es_principal': True,
    }
    actualizados = AlumnoRepresentante.objects.filter(
        alumno=alumno, representante=representante
    ).update(**valores)
    if not actualizados:
        AlumnoRepresentante.objects.create(alumno=alumno, representante=representante, **valores)
    AlumnoRepresentante.objects.filter(alumno=alumno).exclude(
        representante=representante
    ).update(es_principal=False)
    return representante


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

    # Validar formato de fecha requerida (acepta ISO yyyy-mm-dd o dd/mm/yyyy)
    fecha_nacimiento = _a_fecha(data['fecha_nacimiento'])
    if fecha_nacimiento is None:
        return None, 'El campo fecha_nacimiento tiene un formato inválido (use yyyy-mm-dd o dd/mm/yyyy)'

    # Verificar si ya existe un alumno con el mismo número de documento
    if Alumnos.objects.filter(numero_documento_identidad=data['numero_documento_identidad']).exists():
        return None, 'Ya existe un alumno con este número de documento'

    # Verificar si ya existe un alumno con la misma cédula escolar
    if data.get('cedula_escolar') and Alumnos.objects.filter(cedula_escolar=data['cedula_escolar']).exists():
        return None, 'Ya existe un alumno con esta cédula escolar'

    # Crear el alumno (payload plano: todos los campos del modelo Alumnos)
    alumno_data = {
        'primer_nombre': data['primer_nombre'],
        'segundo_nombre': data.get('segundo_nombre') or '',
        'primer_apellido': data['primer_apellido'],
        'segundo_apellido': data.get('segundo_apellido') or '',
        'tipo_documento_identidad': data.get('tipo_documento_identidad') or 'V',
        'numero_documento_identidad': data['numero_documento_identidad'],
        'cedula_escolar': data['cedula_escolar'],
        'fecha_nacimiento': fecha_nacimiento,
        'genero': data.get('genero') or 'Masculino',
        'lugar_nacimiento': data.get('lugar_nacimiento') or '',
        'nacionalidad': data.get('nacionalidad') or 'Venezolana',
        # Lugar de nacimiento administrativo (estado/municipio/parroquia)
        'entidad_federal_nacimiento': data.get('entidad_federal_nacimiento') or None,
        'municipio_nacimiento': data.get('municipio_nacimiento') or None,
        'parroquia_nacimiento': data.get('parroquia_nacimiento') or None,
        # Datos médicos y medidas
        'grupo_sanguineo': data.get('grupo_sanguineo') or 'O+',
        'peso_kg': _a_decimal(data.get('peso_kg')),
        'talla_cm': _a_decimal(data.get('talla_cm')),
        'talla_camisa': data.get('talla_camisa') or None,
        'talla_pantalon': data.get('talla_pantalon') or None,
        'talla_zapato': data.get('talla_zapato') or None,
        'alergico_a': data.get('alergico_a') or None,
        'tratamiento_medico': data.get('tratamiento_medico') or None,
        'condicion_fisica': data.get('condicion_fisica') or None,
        'apoyo_escolar': _a_booleano(data.get('apoyo_escolar')),
        'vacunas_completas': _a_booleano(data.get('vacunas_completas')),
        'discapacidad': _a_booleano(data.get('discapacidad')),
        'tipo_discapacidad': data.get('tipo_discapacidad') or None,
        # Carnet de la Patria y datos bancarios
        'carnet_patria_codigo': data.get('carnet_patria_codigo') or None,
        'carnet_patria_serial': data.get('carnet_patria_serial') or None,
        'numero_cuenta': data.get('numero_cuenta') or None,
        'tipo_cuenta': data.get('tipo_cuenta') or None,
        'banco': data.get('banco') or None,
        # Datos familiares
        'estado_civil_padres': data.get('estado_civil_padres') or None,
        'tipo_vivienda': data.get('tipo_vivienda') or None,
        'profesion_madre': data.get('profesion_madre') or None,
        'profesion_padre': data.get('profesion_padre') or None,
        'numero_hermanos': _a_entero(data.get('numero_hermanos')),
        'numero_en_el_planter': _a_entero(data.get('numero_en_el_planter')),
        'ingreso_familiar': _a_decimal(data.get('ingreso_familiar')),
        'observaciones': data.get('observaciones') or None,
        # Profesor encargado (Docente Guía): cédula o nombre completo (ver _resolver_profesor_encargado)
        'id_profesor_encargado': _resolver_profesor_encargado(data.get('profesor_encargado')),
        'fecha_inscripcion_inicial': _a_fecha(data.get('fecha_inscripcion_inicial')) or date.today(),
        'estatus_general': 'Activo',
    }

    direccion_data = data.get('direccion') or {}

    try:
        with transaction.atomic():
            alumno = Alumnos.objects.create(**alumno_data)

            # Dirección de residencia: se persiste en core.Direcciones y se
            # vincula al alumno (misma lógica que AlumnosSerializer).
            if direccion_data.get('calle') and direccion_data.get('ciudad') and direccion_data.get('estado'):
                direccion = Direcciones.objects.create(
                    calle=direccion_data['calle'],
                    ciudad=direccion_data['ciudad'],
                    estado=direccion_data['estado'],
                    referencia=direccion_data.get('referencia') or None,
                )
                alumno.id_direccion_residencia = direccion
                alumno.save(update_fields=['id_direccion_residencia'])
            elif direccion_data:
                logger.warning(
                    'Dirección incompleta ignorada en webhook (requiere calle, ciudad y estado): %s',
                    direccion_data,
                )

            # Representante legal: requiere cedula, nombre y telefono completos
            # (si está incompleto se ignora con warning, como la dirección).
            representante_data = data.get('representante') or {}
            if (
                representante_data.get('cedula')
                and representante_data.get('nombre')
                and representante_data.get('telefono')
            ):
                _vincular_representante_webhook(alumno, representante_data, data.get('parentesco'))
            elif representante_data:
                logger.warning(
                    'Representante incompleto ignorado en webhook (requiere cedula, nombre y telefono): %s',
                    representante_data,
                )

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
    id_grupo = _a_entero(data.get('id_grupo'))
    if not id_grupo:
        return None, None  # No se solicita inscripción

    try:
        grupo = GruposAcademicos.objects.get(id_grupo=id_grupo)
    except GruposAcademicos.DoesNotExist:
        return None, 'El grupo especificado no existe'

    inscripcion_data = {
        'alumno': alumno,
        'grupo': grupo,
        'fecha_inscripcion': _a_fecha(data.get('fecha_inscripcion')) or datetime.now(),
        'estado_inscripcion': data.get('estado_inscripcion') or 'Activa',
        'monto_pago': _a_decimal(data.get('monto_pago')),
        'referencia_bancaria': data.get('referencia_bancaria') or None,
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
