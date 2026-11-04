"""
Business logic for enrollment/inscription operations.
"""
import re
import logging
from django.utils import timezone
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from ..models import Inscripciones
from apps.core.models import ConfiguracionPlantel
from ..reports import _crear_estilos_comprobante, _texto_seguro, _tabla_clave_valor

logger = logging.getLogger(__name__)


def generar_comprobante_inscripcion(inscripcion_id):
    """
    Genera el comprobante de inscripción en PDF de un alumno.
    Incluye datos del plantel, datos personales, tallas de uniforme, datos médicos,
    grupo académico asignado y datos de la inscripción.

    Returns:
        HttpResponse: PDF response or None if error
    """
    try:
        inscripcion = Inscripciones.objects.select_related(
            'alumno', 'grupo', 'grupo__periodo', 'grupo__nivel',
            'grupo__grado', 'grupo__seccion', 'grupo__turno'
        ).get(id_inscripcion=inscripcion_id)
    except Inscripciones.DoesNotExist:
        return None

    try:
        alumno = inscripcion.alumno
        grupo = inscripcion.grupo
        plantel = ConfiguracionPlantel.objects.first()
        estilos = _crear_estilos_comprobante()

        identificador = re.sub(r'[^\w-]', '_', alumno.cedula_escolar or str(inscripcion.id_inscripcion))
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="comprobante_inscripcion_{identificador}.pdf"'

        doc = SimpleDocTemplate(
            response, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=40, bottomMargin=40
        )
        story = []

        def seccion(titulo, filas):
            story.append(Paragraph(titulo, estilos['subtitulo']))
            story.append(_tabla_clave_valor(filas, estilos))
            story.append(Spacer(1, 12))

        story.append(Paragraph("COMPROBANTE DE INSCRIPCIÓN", estilos['titulo']))
        story.append(Spacer(1, 6))
        fecha_emision = timezone.localtime().strftime('%d/%m/%Y %H:%M:%S')
        story.append(Paragraph(f"Fecha de emisión: {fecha_emision}", estilos['normal']))
        story.append(Spacer(1, 12))

        seccion("DATOS DEL PLANTEL", [
            ('Plantel:', _texto_seguro(plantel.nombre_plantel if plantel else None, 'PLATAFORMA ESCOLAR')),
            ('Código del Plantel:', _texto_seguro(plantel.codigo_plantel if plantel else None)),
            ('Código Estadístico:', _texto_seguro(plantel.codigo_estadistico if plantel else None)),
            ('Código DEA:', _texto_seguro(plantel.codigo_dea if plantel else None)),
        ])

        nombre_completo = ' '.join(filter(None, [
            alumno.primer_nombre, alumno.segundo_nombre, alumno.primer_apellido, alumno.segundo_apellido
        ]))
        seccion("DATOS PERSONALES DEL ALUMNO", [
            ('Nombre Completo:', _texto_seguro(nombre_completo)),
            ('Tipo de Documento:', _texto_seguro(alumno.tipo_documento_identidad)),
            ('Número de Documento:', _texto_seguro(alumno.numero_documento_identidad)),
            ('Cédula Escolar:', _texto_seguro(alumno.cedula_escolar)),
            ('Fecha de Nacimiento:', _texto_seguro(
                alumno.fecha_nacimiento.strftime('%d/%m/%Y') if alumno.fecha_nacimiento else None)),
            ('Género:', _texto_seguro(alumno.genero)),
            ('Nacionalidad:', _texto_seguro(alumno.nacionalidad)),
            ('Lugar de Nacimiento:', _texto_seguro(alumno.lugar_nacimiento)),
        ])

        seccion("TALLAS DE UNIFORME Y MEDIDAS", [
            ('Talla de Camisa:', _texto_seguro(alumno.talla_camisa)),
            ('Talla de Pantalón:', _texto_seguro(alumno.talla_pantalon)),
            ('Talla de Zapato:', _texto_seguro(alumno.talla_zapato)),
            ('Peso:', _texto_seguro(f"{alumno.peso_kg} kg" if alumno.peso_kg is not None else None)),
            ('Estatura:', _texto_seguro(f"{alumno.talla_cm} cm" if alumno.talla_cm is not None else None)),
        ])

        seccion("DATOS MÉDICOS", [
            ('Grupo Sanguíneo:', _texto_seguro(alumno.grupo_sanguineo)),
            ('Alergias:', _texto_seguro(alumno.alergico_a, 'Ninguna')),
            ('Tratamiento Médico:', _texto_seguro(alumno.tratamiento_medico, 'Ninguno')),
            ('Condición Física:', _texto_seguro(alumno.condicion_fisica)),
            ('Discapacidad:', 'Sí' if alumno.discapacidad else 'No'),
            ('Tipo de Discapacidad:', _texto_seguro(alumno.tipo_discapacidad)),
        ])

        seccion("GRUPO ACADÉMICO ASIGNADO", [
            ('Período Académico:', _texto_seguro(grupo.periodo.nombre_periodo if grupo.periodo else None)),
            ('Nivel:', _texto_seguro(grupo.nivel.nombre_nivel if grupo.nivel else None)),
            ('Grado:', _texto_seguro(grupo.grado.nombre_grado if grupo.grado else None)),
            ('Sección:', _texto_seguro(grupo.seccion.nombre_seccion if grupo.seccion else None)),
            ('Turno:', _texto_seguro(grupo.turno.nombre_turno if grupo.turno else None)),
        ])

        fecha_inscripcion = None
        if inscripcion.fecha_inscripcion:
            fecha_inscripcion = timezone.localtime(inscripcion.fecha_inscripcion).strftime('%d/%m/%Y %H:%M')
        seccion("DATOS DE LA INSCRIPCIÓN", [
            ('N° de Inscripción:', _texto_seguro(inscripcion.id_inscripcion)),
            ('Fecha de Inscripción:', _texto_seguro(fecha_inscripcion)),
            ('Estado:', _texto_seguro(inscripcion.estado_inscripcion)),
            ('Monto de Pago:', _texto_seguro(
                f"Bs. {inscripcion.monto_pago}" if inscripcion.monto_pago is not None else None)),
            ('Referencia Bancaria:', _texto_seguro(inscripcion.referencia_bancaria)),
        ])

        story.append(Spacer(1, 10))
        story.append(Paragraph("Este documento es un comprobante de inscripción.", estilos['normal']))
        story.append(Paragraph(
            "Para cualquier duda o aclaración, contacte a la administración del plantel.", estilos['normal']
        ))

        doc.build(story)
        return response

    except Exception:
        logger.exception('Error al generar el comprobante de inscripción %s', inscripcion_id)
        return None
