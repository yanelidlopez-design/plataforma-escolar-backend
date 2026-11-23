"""
Generador de PDF y Excel para Constancia de Prosecución en el Nivel de Educación Primaria.
Formato oficial del Ministerio del Poder Popular para la Educación (Venezuela).
"""
import io
import logging
import re

from django.utils import timezone
from django.utils.text import get_valid_filename
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    PageBreak,
)
from html import escape

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

from .models import (
    Alumnos,
    ConstanciaProsecucionFinal,
    ConfiguracionInstitucional,
)

logger = logging.getLogger(__name__)

MESES = (
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
)


def _estilos():
    estilo_membrete_1 = ParagraphStyle(
        'Membrete1', fontName='Helvetica-Bold', fontSize=13, leading=16,
        alignment=TA_CENTER, textColor=colors.HexColor('#1a3a5c'),
    )
    estilo_membrete_2 = ParagraphStyle(
        'Membrete2', fontName='Helvetica', fontSize=11, leading=15,
        alignment=TA_CENTER, textColor=colors.HexColor('#1a3a5c'),
    )
    estilo_membrete_3 = ParagraphStyle(
        'Membrete3', fontName='Helvetica-Bold', fontSize=12, leading=16,
        alignment=TA_CENTER, textColor=colors.HexColor('#1a3a5c'),
    )
    estilo_membrete_4 = ParagraphStyle(
        'Membrete4', fontName='Helvetica', fontSize=9, leading=13,
        alignment=TA_CENTER, textColor=colors.HexColor('#4a4a4a'),
    )
    estilo_titulo = ParagraphStyle(
        'TituloConstancia', fontName='Helvetica-Bold', fontSize=13, leading=17,
        alignment=TA_CENTER, textColor=colors.HexColor('#1a3a5c'), spaceAfter=12,
    )
    estilo_cuerpo = ParagraphStyle(
        'CuerpoConstancia', fontName='Helvetica', fontSize=11, leading=19,
        alignment=TA_JUSTIFY, textColor=colors.HexColor('#222222'),
        spaceAfter=8, firstLineIndent=36,
    )
    estilo_firma = ParagraphStyle(
        'FirmaConstancia', fontName='Helvetica', fontSize=8.5, leading=12,
        alignment=TA_CENTER, textColor=colors.HexColor('#333333'),
    )
    return (
        estilo_membrete_1, estilo_membrete_2, estilo_membrete_3,
        estilo_membrete_4, estilo_titulo, estilo_cuerpo, estilo_firma,
    )


def _datos_institucionales():
    try:
        config = ConfiguracionInstitucional.get_solo()
    except Exception:  # nosec B101
        logger.debug('Error obteniendo ConfiguracionInstitucional', exc_info=True)
        config = None

    if config:
        return {
            'nombre_institucion': config.nombre_institucion,
            'municipio': config.municipio,
            'parroquia': config.parroquia,
            'cdce_estadal': config.cdce_estadal,
            'director_institucion_nombre': config.director_institucion_nombre,
            'director_institucion_cedula': config.director_institucion_cedula,
            'director_cdce_nombre': config.director_cdce_nombre,
            'director_cdce_cedula': config.director_cdce_cedula,
        }
    return {
        'nombre_institucion': '_______________________',
        'municipio': '_______________________',
        'parroquia': '_______________________',
        'cdce_estadal': '_______________________',
        'director_institucion_nombre': '_______________________',
        'director_institucion_cedula': 'V.-__________',
        'director_cdce_nombre': '_______________________',
        'director_cdce_cedula': 'V.-__________',
    }


def _frase_grado(valor):
    texto = str(valor or '__________').strip()
    if 'grado' in texto.lower():
        return texto
    return f'{texto} Grado'


def _constancia_story(alumno_objeto, constancia_objeto, estilos, lugar_expedicion_override=None):
    (
        estilo_membrete_1, estilo_membrete_2, estilo_membrete_3,
        estilo_membrete_4, estilo_titulo, estilo_cuerpo, estilo_firma,
    ) = estilos

    datos_inst = _datos_institucionales()
    director_nombre = escape(datos_inst['director_institucion_nombre'])
    director_cedula = escape(datos_inst['director_institucion_cedula'])
    nombre_plantel = escape(datos_inst['nombre_institucion'])
    municipio_plantel = escape(datos_inst['municipio'])
    parroquia_plantel = escape(datos_inst['parroquia'])
    centro_estadal = escape(datos_inst['cdce_estadal'])

    nombre_alumno = escape(' '.join(filter(None, [
        alumno_objeto.primer_nombre,
        alumno_objeto.segundo_nombre,
        alumno_objeto.primer_apellido,
        alumno_objeto.segundo_apellido,
    ])).strip() or '_______________________')

    cedula_alumno = escape(
        alumno_objeto.cedula_escolar
        or alumno_objeto.numero_documento_identidad
        or '__________'
    )
    documento_alumno = escape(alumno_objeto.numero_documento_identidad or '__________')
    municipio_alumno = escape(
        alumno_objeto.municipio_nacimiento
        or alumno_objeto.lugar_nacimiento
        or '__________'
    )
    estado_alumno = escape(
        alumno_objeto.entidad_federal_nacimiento or '__________'
    )

    fecha_nacimiento_texto = '__________'
    if alumno_objeto.fecha_nacimiento:
        fecha_nacimiento_texto = (
            f'{alumno_objeto.fecha_nacimiento.day} de '
            f'{MESES[alumno_objeto.fecha_nacimiento.month - 1]} de '
            f'{alumno_objeto.fecha_nacimiento.year}'
        )

    grado_cursado = constancia_objeto.grado_cursado or '__________'
    if not constancia_objeto.grado_cursado:
        try:
            inscripcion_ref = (
                alumno_objeto.inscripciones
                .select_related('grupo__grado')
                .filter(estado_inscripcion__in=['Activa', 'Graduado'])
                .first()
            )
            if inscripcion_ref and inscripcion_ref.grupo_id:
                grado_cursado = (
                    inscripcion_ref.grupo.grado.nombre_grado or '__________'
                )
        except Exception:  # nosec B101
            logger.debug(
                'Error resolviendo grado cursado del alumno %s',
                getattr(alumno_objeto, 'pk', None), exc_info=True,
            )

    literal_final = escape(str(constancia_objeto.literal_final or '____'))
    periodo_escolar = escape(str(constancia_objeto.periodo_escolar or '__________'))
    siguiente_grado = escape(_frase_grado(constancia_objeto.promovido_al_grado))
    grado_cursado_frase = escape(_frase_grado(grado_cursado))

    lugar = lugar_expedicion_override or constancia_objeto.lugar_expedicion or '__________'

    story = []
    story.append(Paragraph('República Bolivariana de Venezuela', estilo_membrete_1))
    story.append(Paragraph('Ministerio del Poder Popular para la Educación', estilo_membrete_2))
    story.append(Paragraph(nombre_plantel, estilo_membrete_3))
    story.append(Paragraph('Cod. DEA: OD12431208 | Calabozo - El Calvario', estilo_membrete_4))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor('#1a3a5c')))
    story.append(Spacer(1, 14))

    story.append(Paragraph(
        'CONSTANCIA DE PROSECUCIÓN EN EL NIVEL DE EDUCACIÓN PRIMARIA',
        estilo_titulo,
    ))
    story.append(Spacer(1, 6))

    cuerpo_texto = (
        f'Quien suscribe <b>{director_nombre}</b>, titular de la Cédula de '
        f'Identidad N° {director_cedula}, Director(a) de la Institución '
        f'Educativa <b>{nombre_plantel}</b>, ubicada en el Municipio '
        f'{municipio_plantel} de la Parroquia {parroquia_plantel}, '
        'adscrita al Centro de Desarrollo de la Calidad Educativa Estadal '
        f'{centro_estadal}. Por la presente hace constar que el (la) '
        f'estudiante <b>{nombre_alumno}</b>, titular de la Cédula Escolar N° '
        f'{cedula_alumno}, Cédula de Identidad N° o Pasaporte N° {documento_alumno}, '
        'nacido (a) en el Municipio '
        f'{municipio_alumno} del Estado {estado_alumno}, en fecha '
        f'{fecha_nacimiento_texto}, cursó el {grado_cursado_frase}, '
        f'correspondiéndole el literal <b>{literal_final}</b> durante el periodo '
        f'escolar {periodo_escolar}, siendo promovido (a) al '
        f'<b>{siguiente_grado}</b> del Nivel de Educación Primaria.'
    )
    story.append(Paragraph(cuerpo_texto, estilo_cuerpo))
    story.append(Spacer(1, 8))

    fecha_expedicion = constancia_objeto.fecha_expedicion or timezone.localdate()
    expedicion_texto = (
        f'Constancia que se expide en {escape(lugar)}, a los '
        f'{fecha_expedicion.day} días del mes de '
        f'{MESES[fecha_expedicion.month - 1]} de {fecha_expedicion.year}.'
    )
    story.append(Paragraph(expedicion_texto, estilo_cuerpo))
    story.append(Spacer(1, 44))

    director_cdce_nombre = escape(datos_inst['director_cdce_nombre'])
    director_cdce_cedula = escape(datos_inst['director_cdce_cedula'])

    celda_institucion = Paragraph(
        '<b>INSTITUCIÓN EDUCATIVA<br/>DIRECTOR(A)</b><br/><br/>'
        f'Nombre y Apellido: {director_nombre}<br/>'
        f'Número de C.I.: {director_cedula}<br/><br/>'
        'Firma y Sello',
        estilo_firma,
    )
    celda_cdcee = Paragraph(
        '<b>CENTRO DE DESARROLLO DE LA CALIDAD<br/>'
        'EDUCATIVA ESTADAL<br/>DIRECTOR(A)</b><br/><br/>'
        f'Nombre y Apellido: {director_cdce_nombre}<br/>'
        f'Número de C.I.: {director_cdce_cedula}<br/><br/>'
        'Firma y Sello',
        estilo_firma,
    )

    tabla_firmas = Table(
        [[celda_institucion, celda_cdcee]],
        colWidths=[8.5 * cm, 8.5 * cm],
    )
    tabla_firmas.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LINEABOVE', (0, 0), (0, 0), 0.8, colors.black),
        ('LINEABOVE', (2, 0), (2, 0), 0.8, colors.black),
    ]))
    story.append(tabla_firmas)

    return story


def generar_pdf_constancia_procesion(alumno_objeto, constancia_objeto, lugar_expedicion_override=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=f'Constancia de Procesion - {alumno_objeto}',
        author=_datos_institucionales()['nombre_institucion'],
        subject='Constancia de Procesion en el Nivel de Educacion Primaria',
    )

    estilos = _estilos()
    story = _constancia_story(
        alumno_objeto, constancia_objeto, estilos, lugar_expedicion_override
    )

    doc.build(story)
    buffer.seek(0)

    cedula = (
        alumno_objeto.cedula_escolar
        or alumno_objeto.numero_documento_identidad
        or alumno_objeto.id_alumno
    )
    filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', f'Constancia_Procesion_{cedula}.pdf')
    return buffer, filename


def generar_constancias_lote_pdf(constancias_queryset, lugar_expedicion_override=None):
    constancias = list(constancias_queryset.select_related('alumno'))
    if not constancias:
        raise ValueError('No hay constancias para generar el lote.')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title='Constancias de Procesion - Lote',
        author='Institucion Educativa',
        subject='Constancias de Procesion en el Nivel de Educacion Primaria',
    )

    estilos = _estilos()
    story = []

    total = len(constancias)
    for idx, constancia in enumerate(constancias):
        alumno = constancia.alumno
        story.extend(
            _constancia_story(
                alumno, constancia, estilos, lugar_expedicion_override
            )
        )
        if idx < total - 1:
            story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)

    periodo = constancias[0].periodo_escolar or 'lote'
    filename = get_valid_filename(f'Constancias_Procesion_{periodo}.pdf')
    return buffer, filename

# ============================================================================
# GENERACIÓN DE EXCEL (.xlsx) - Constancia de Prosecución
# ============================================================================

_TITLE_FONT = Font(name='Calibri', bold=True, size=14, color='1A3A5C')
_HEADER_FONT = Font(name='Calibri', bold=True, size=11, color='1A3A5C')
_BODY_FONT = Font(name='Calibri', size=11, color='222222')
_SIGNATURE_FONT = Font(name='Calibri', size=10, color='333333')
_SIGNATURE_BOLD = Font(name='Calibri', bold=True, size=10, color='333333')

_TITLE_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)
_BODY_ALIGN = Alignment(horizontal='justify', vertical='top', wrap_text=True)
_SIGNATURE_ALIGN = Alignment(horizontal='center', vertical='top', wrap_text=True)

_THIN_BORDER = Border(
    left=Side(style='thin', color='000000'),
    right=Side(style='thin', color='000000'),
    top=Side(style='thin', color='000000'),
    bottom=Side(style='thin', color='000000'),
)


def _estimar_altura_fila(texto, ancho_caracteres=95, altura_min=30):
    """Estima la altura de fila necesaria para que el texto quepa con wrap_text."""
    if not texto:
        return altura_min
    chars_por_linea = max(40, ancho_caracteres)
    lineas = max(1, (len(texto) + chars_por_linea - 1) // chars_por_linea)
    altura = max(altura_min, lineas * 15 + 10)
    return min(altura, 300)


def _constancia_excel_body_text(alumno_objeto, constancia_objeto, datos_inst, lugar_expedicion_override=None):
    """Construye los textos del cuerpo de la constancia para Excel."""
    director_nombre = datos_inst['director_institucion_nombre'] or '_______________________'
    director_cedula = datos_inst['director_institucion_cedula'] or 'V.-__________'
    nombre_plantel = datos_inst['nombre_institucion'] or '_______________________'
    municipio_plantel = datos_inst['municipio'] or '_______________________'
    parroquia_plantel = datos_inst['parroquia'] or '_______________________'
    centro_estadal = datos_inst['cdce_estadal'] or '_______________________'

    nombre_alumno = ' '.join(filter(None, [
        alumno_objeto.primer_nombre,
        alumno_objeto.segundo_nombre,
        alumno_objeto.primer_apellido,
        alumno_objeto.segundo_apellido,
    ])).strip() or '_______________________'

    cedula_alumno = (
        alumno_objeto.cedula_escolar
        or alumno_objeto.numero_documento_identidad
        or '__________'
    )
    documento_alumno = alumno_objeto.numero_documento_identidad or '__________'
    municipio_alumno = (
        alumno_objeto.municipio_nacimiento
        or alumno_objeto.lugar_nacimiento
        or '__________'
    )
    estado_alumno = alumno_objeto.entidad_federal_nacimiento or '__________'

    fecha_nacimiento_texto = '__________'
    if alumno_objeto.fecha_nacimiento:
        fecha_nacimiento_texto = (
            f'{alumno_objeto.fecha_nacimiento.day} de '
            f'{MESES[alumno_objeto.fecha_nacimiento.month - 1]} de '
            f'{alumno_objeto.fecha_nacimiento.year}'
        )

    grado_cursado = constancia_objeto.grado_cursado or '__________'
    if not constancia_objeto.grado_cursado:
        try:
            inscripcion_ref = (
                alumno_objeto.inscripciones
                .select_related('grupo__grado')
                .filter(estado_inscripcion__in=['Activa', 'Graduado'])
                .first()
            )
            if inscripcion_ref and inscripcion_ref.grupo_id:
                grado_cursado = (
                    inscripcion_ref.grupo.grado.nombre_grado or '__________'
                )
        except Exception:
            logger.debug(
                'Error resolviendo grado cursado del alumno %s',
                getattr(alumno_objeto, 'pk', None), exc_info=True,
            )

    literal_final = str(constancia_objeto.literal_final or '____')
    periodo_escolar = str(constancia_objeto.periodo_escolar or '__________')
    siguiente_grado = _frase_grado(constancia_objeto.promovido_al_grado)
    grado_cursado_frase = _frase_grado(grado_cursado)

    lugar = lugar_expedicion_override or constancia_objeto.lugar_expedicion or '__________'

    cuerpo_texto = (
        f'Quien suscribe {director_nombre}, titular de la Cédula de Identidad N° {director_cedula}, '
        f'Director(a) de la Institución Educativa {nombre_plantel}, ubicada en el Municipio '
        f'{municipio_plantel} de la Parroquia {parroquia_plantel}, adscrita al Centro de '
        f'Desarrollo de la Calidad Educativa Estadal {centro_estadal}. Por la presente hace constar '
        f'que el (la) estudiante {nombre_alumno}, titular de la Cédula Escolar N° {cedula_alumno}, '
        f'Cédula de Identidad N° o Pasaporte N° {documento_alumno}, nacido (a) en el Municipio '
        f'{municipio_alumno} del Estado {estado_alumno}, en fecha {fecha_nacimiento_texto}, '
        f'cursó el {grado_cursado_frase}, correspondiéndole el literal {literal_final} durante el '
        f'periodo escolar {periodo_escolar}, siendo promovido (a) al {siguiente_grado} del '
        f'Nivel de Educación Primaria.'
    )

    fecha_expedicion = constancia_objeto.fecha_expedicion or timezone.localdate()
    expedicion_texto = (
        f'Constancia que se expide en {lugar}, a los '
        f'{fecha_expedicion.day} días del mes de '
        f'{MESES[fecha_expedicion.month - 1]} de {fecha_expedicion.year}.'
    )

    return cuerpo_texto, expedicion_texto, {
        'director_institucion_nombre': director_nombre,
        'director_institucion_cedula': director_cedula,
        'director_cdce_nombre': datos_inst['director_cdce_nombre'] or '_______________________',
        'director_cdce_cedula': datos_inst['director_cdce_cedula'] or 'V.-__________',
        'nombre_institucion': nombre_plantel,
        'municipio': municipio_plantel,
        'parroquia': parroquia_plantel,
        'cdce_estadal': centro_estadal,
    }


def generar_xlsx_constancia_procesion(
    alumno_objeto,
    constancia_objeto,
    lugar_expedicion_override=None,
):
    """
    Genera un archivo Excel (.xlsx) con una constancia de prosecución
    lista para imprimir en tamaño Carta.

    Retorna (io.BytesIO, filename).
    """
    datos_inst = _datos_institucionales()
    cuerpo_texto, expedicion_texto, firma_datos = _constancia_excel_body_text(
        alumno_objeto, constancia_objeto, datos_inst, lugar_expedicion_override
    )

    wb = Workbook()
    ws = wb.active
    ws.title = 'Constancia_Prosecucion'

    ws.page_setup.orientation = 'portrait'
    ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
    ws.page_margins.left = 0.7
    ws.page_margins.right = 0.7
    ws.page_margins.top = 0.7
    ws.page_margins.bottom = 0.7
    ws.page_margins.header = 0.3
    ws.page_margins.footer = 0.3

    for col in range(1, 9):
        col_letter = get_column_letter(col)
        ws.column_dimensions[col_letter].width = 15

    for fila in range(1, 6):
        ws.row_dimensions[fila].height = 24
        ws.merge_cells(f'A{fila}:H{fila}')

    ws.merge_cells('A6:H6')
    celda_titulo = ws['A6']
    celda_titulo.value = 'CONSTANCIA DE PROSECUCIÓN EN EL NIVEL DE EDUCACIÓN PRIMARIA'
    celda_titulo.font = _TITLE_FONT
    celda_titulo.alignment = _TITLE_ALIGN
    ws.row_dimensions[6].height = 30

    ws.merge_cells('A7:H7')
    ws.row_dimensions[7].height = 10

    ws.merge_cells('A8:H9')
    celda_cuerpo = ws['A8']
    celda_cuerpo.value = cuerpo_texto
    celda_cuerpo.font = _BODY_FONT
    celda_cuerpo.alignment = _BODY_ALIGN
    altura_cuerpo = _estimar_altura_fila(cuerpo_texto, ancho_caracteres=110, altura_min=60)
    ws.row_dimensions[8].height = altura_cuerpo

    ws.merge_cells('A10:H10')
    ws.row_dimensions[10].height = 10

    ws.merge_cells('A11:H11')
    celda_expedicion = ws['A11']
    celda_expedicion.value = expedicion_texto
    celda_expedicion.font = _BODY_FONT
    celda_expedicion.alignment = _BODY_ALIGN
    ws.row_dimensions[11].height = 30

    ws.merge_cells('A12:H13')
    ws.row_dimensions[12].height = 20

    firma_inst = (
        'INSTITUCIÓN EDUCATIVA\n'
        'DIRECTOR(A)\n\n'
        f'Nombre y Apellido: {firma_datos["director_institucion_nombre"]}\n'
        f'Número de C.I.: {firma_datos["director_institucion_cedula"]}\n\n'
        'Firma y Sello:'
    )
    firma_cdce = (
        'CENTRO DE DESARROLLO DE LA CALIDAD EDUCATIVA ESTADAL\n'
        'DIRECTOR(A)\n\n'
        f'Nombre y Apellido: {firma_datos["director_cdce_nombre"]}\n'
        f'Número de C.I.: {firma_datos["director_cdce_cedula"]}\n\n'
        'Firma y Sello:'
    )

    ws.merge_cells('A14:D22')
    ws.merge_cells('E14:H22')

    celda_f1 = ws['A14']
    celda_f1.value = firma_inst
    celda_f1.font = _SIGNATURE_FONT
    celda_f1.alignment = Alignment(horizontal='center', vertical='top', wrap_text=True)

    celda_f2 = ws['E14']
    celda_f2.value = firma_cdce
    celda_f2.font = _SIGNATURE_FONT
    celda_f2.alignment = Alignment(horizontal='center', vertical='top', wrap_text=True)

    for fila in range(14, 23):
        for col in range(1, 9):
            ws.cell(row=fila, column=col).border = _THIN_BORDER

    ws.row_dimensions[14].height = 95

    cedula = (
        alumno_objeto.cedula_escolar
        or alumno_objeto.numero_documento_identidad
        or alumno_objeto.id_alumno
    )
    filename = re.sub(
        r'[^a-zA-Z0-9_.-]',
        '_',
        f'Constancia_Prosecucion_{cedula}.xlsx',
    )

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer, filename


def generar_xlsx_constancias_lote(
    constancias_queryset,
    lugar_expedicion_override=None,
):
    """
    Genera un archivo Excel (.xlsx) con una pestaña por cada alumno
    del queryset. Cada pestaña tiene el mismo diseño de impresión.

    Retorna (io.BytesIO, filename).
    """
    constancias = list(constancias_queryset.select_related('alumno'))
    if not constancias:
        raise ValueError('No hay constancias para generar el lote.')

    wb = Workbook()
    wb.remove(wb.active)

    for constancia in constancias:
        alumno = constancia.alumno
        cedula = (
            alumno.cedula_escolar
            or alumno.numero_documento_identidad
            or str(alumno.id_alumno)
        )
        nombre_hoja = re.sub(r'[^A-Za-z0-9_]', '_', cedula)[:31]

        contador = 1
        nombre_hoja_original = nombre_hoja
        while nombre_hoja in wb.sheetnames:
            nombre_hoja = f'{nombre_hoja_original[:27]}_{contador}'
            contador += 1

        ws = wb.create_sheet(title=nombre_hoja)

        datos_inst = _datos_institucionales()
        cuerpo_texto, expedicion_texto, firma_datos = _constancia_excel_body_text(
            alumno, constancia, datos_inst, lugar_expedicion_override
        )

        ws.page_setup.orientation = 'portrait'
        ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
        ws.page_margins.left = 0.7
        ws.page_margins.right = 0.7
        ws.page_margins.top = 0.7
        ws.page_margins.bottom = 0.7

        for col in range(1, 9):
            col_letter = get_column_letter(col)
            ws.column_dimensions[col_letter].width = 15

        for fila in range(1, 6):
            ws.row_dimensions[fila].height = 24
            ws.merge_cells(f'A{fila}:H{fila}')

        ws.merge_cells('A6:H6')
        celda_titulo = ws['A6']
        celda_titulo.value = 'CONSTANCIA DE PROSECUCIÓN EN EL NIVEL DE EDUCACIÓN PRIMARIA'
        celda_titulo.font = _TITLE_FONT
        celda_titulo.alignment = _TITLE_ALIGN
        ws.row_dimensions[6].height = 30

        ws.merge_cells('A7:H7')
        ws.row_dimensions[7].height = 10

        ws.merge_cells('A8:H9')
        celda_cuerpo = ws['A8']
        celda_cuerpo.value = cuerpo_texto
        celda_cuerpo.font = _BODY_FONT
        celda_cuerpo.alignment = _BODY_ALIGN
        altura_cuerpo = _estimar_altura_fila(cuerpo_texto, ancho_caracteres=110, altura_min=60)
        ws.row_dimensions[8].height = altura_cuerpo

        ws.merge_cells('A10:H10')
        ws.row_dimensions[10].height = 10

        ws.merge_cells('A11:H11')
        celda_expedicion = ws['A11']
        celda_expedicion.value = expedicion_texto
        celda_expedicion.font = _BODY_FONT
        celda_expedicion.alignment = _BODY_ALIGN
        ws.row_dimensions[11].height = 30

        ws.merge_cells('A12:H13')
        ws.row_dimensions[12].height = 20

        firma_inst = (
            'INSTITUCIÓN EDUCATIVA\n'
            'DIRECTOR(A)\n\n'
            f'Nombre y Apellido: {firma_datos["director_institucion_nombre"]}\n'
            f'Número de C.I.: {firma_datos["director_institucion_cedula"]}\n\n'
            'Firma y Sello:'
        )
        firma_cdce = (
            'CENTRO DE DESARROLLO DE LA CALIDAD EDUCATIVA ESTADAL\n'
            'DIRECTOR(A)\n\n'
            f'Nombre y Apellido: {firma_datos["director_cdce_nombre"]}\n'
            f'Número de C.I.: {firma_datos["director_cdce_cedula"]}\n\n'
            'Firma y Sello:'
        )

        ws.merge_cells('A14:D22')
        ws.merge_cells('E14:H22')

        celda_f1 = ws['A14']
        celda_f1.value = firma_inst
        celda_f1.font = _SIGNATURE_FONT
        celda_f1.alignment = Alignment(horizontal='center', vertical='top', wrap_text=True)

        celda_f2 = ws['E14']
        celda_f2.value = firma_cdce
        celda_f2.font = _SIGNATURE_FONT
        celda_f2.alignment = Alignment(horizontal='center', vertical='top', wrap_text=True)

        for fila in range(14, 23):
            for col in range(1, 9):
                ws.cell(row=fila, column=col).border = _THIN_BORDER

        ws.row_dimensions[14].height = 95

    periodo = constancias[0].periodo_escolar or 'lote'
    filename = get_valid_filename(f'Constancias_Prosecucion_{periodo}.xlsx')

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer, filename
