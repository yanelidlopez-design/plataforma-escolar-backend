"""
Generador oficial de Constancia de Prosecución en el Nivel de Educación Primaria
en formato Word (.docx), según especificaciones y estructura del Ministerio
del Poder Popular para la Educación (Venezuela).
"""
import io
import os
import logging
from typing import Optional, Tuple, Sequence
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.text import get_valid_filename

import docx
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

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

ORDINALES = {
    '1': 'Primer',
    '2': 'Segundo',
    '3': 'Tercer',
    '4': 'Cuarto',
    '5': 'Quinto',
    '6': 'Sexto',
}


def _frase_grado(texto: Optional[str]) -> str:
    """Normaliza el nombre del grado a formato 'Primer', 'Segundo', etc."""
    if not texto:
        return '__________'
    t = str(texto).strip()
    partes = t.split()
    primero = partes[0] if partes else ''
    if primero in ORDINALES:
        return ORDINALES[primero]
    limpio = primero.replace('°', '').replace('º', '')
    if limpio in ORDINALES:
        return ORDINALES[limpio]
    for digito, palabra in ORDINALES.items():
        if palabra.lower() in t.lower():
            return palabra
    return t


def _datos_institucionales():
    """Recupera la configuración institucional singleton."""
    try:
        config = ConfiguracionInstitucional.get_solo()
    except Exception:
        logger.debug('Error obteniendo ConfiguracionInstitucional', exc_info=True)
        config = None

    if config:
        return {
            'nombre_institucion': config.nombre_institucion or '_______________________',
            'municipio': config.municipio or '_______________________',
            'parroquia': config.parroquia or '_______________________',
            'cdce_estadal': config.cdce_estadal or '_______________________',
            'director_institucion_nombre': config.director_institucion_nombre or '_______________________',
            'director_institucion_cedula': config.director_institucion_cedula or '__________',
            'director_cdce_nombre': config.director_cdce_nombre or '_______________________',
            'director_cdce_cedula': config.director_cdce_cedula or '__________',
        }
    return {
        'nombre_institucion': '_______________________',
        'municipio': '_______________________',
        'parroquia': '_______________________',
        'cdce_estadal': '_______________________',
        'director_institucion_nombre': '_______________________',
        'director_institucion_cedula': '__________',
        'director_cdce_nombre': '_______________________',
        'director_cdce_cedula': '__________',
    }


def _configurar_seccion(section):
    """Establece tamaño de página Carta y márgenes de 2.0 cm."""
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)


def _agregar_encabezado(doc):
    """Agrega logo y escudo si existen, o el espacio institucional reservado."""
    static_img_dir = Path(settings.BASE_DIR) / 'backend' / 'static' / 'img'
    logo_path = static_img_dir / 'logo_mppe.png'
    escudo_path = static_img_dir / 'escudo_estado.png'

    # Párrafo superior / logo MPPE
    p_logo = doc.add_paragraph()
    p_logo.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_logo.paragraph_format.space_before = Pt(0)
    p_logo.paragraph_format.space_after = Pt(4)

    if logo_path.is_file():
        try:
            p_logo.add_run().add_picture(str(logo_path), width=Inches(2.4))
        except Exception as e:
            logger.debug('No se pudo insertar logo_mppe.png: %s', e)
            r = p_logo.add_run('Ministerio del Poder Popular para la Educación')
            r.font.name = 'Arial'
            r.font.size = Pt(10)
            r.font.bold = True
    else:
        r = p_logo.add_run('Ministerio del Poder Popular para la Educación')
        r.font.name = 'Arial'
        r.font.size = Pt(10)
        r.font.bold = True

    # Párrafo central / escudo
    p_escudo = doc.add_paragraph()
    p_escudo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_escudo.paragraph_format.space_before = Pt(4)
    p_escudo.paragraph_format.space_after = Pt(10)

    if escudo_path.is_file():
        try:
            p_escudo.add_run().add_picture(str(escudo_path), width=Inches(1.2))
        except Exception as e:
            logger.debug('No se pudo insertar escudo_estado.png: %s', e)
    else:
        # Espacio limpio reservado para el escudo
        p_escudo.paragraph_format.space_after = Pt(14)


def _agregar_cuerpo_constancia(doc, alumno: Alumnos, constancia: ConstanciaProsecucionFinal):
    """Genera el contenido formal de una constancia de prosecución."""
    datos_inst = _datos_institucionales()

    # Nombre completo del alumno
    nombre_alumno = ' '.join(
        p for p in [
            alumno.primer_apellido,
            alumno.segundo_apellido,
            alumno.primer_nombre,
            alumno.segundo_nombre,
        ] if p
    ).strip() or '________________________________'

    # Documento de identidad del alumno
    cedula_alumno = alumno.cedula_escolar or alumno.numero_documento_identidad or '__________'

    # Municipio y Estado de nacimiento
    municipio_nac = alumno.municipio_nacimiento or alumno.lugar_nacimiento or '__________'
    estado_nac = alumno.entidad_federal_nacimiento or '__________'

    # Fecha de nacimiento
    if alumno.fecha_nacimiento:
        fecha_nac_str = (
            f"{alumno.fecha_nacimiento.day} de "
            f"{MESES[alumno.fecha_nacimiento.month - 1]} de "
            f"{alumno.fecha_nacimiento.year}"
        )
    else:
        fecha_nac_str = '__________'

    # Grado cursado y promovido
    grado_cursado = _frase_grado(constancia.grado_cursado)
    literal = constancia.literal_final or '____'
    periodo_escolar = constancia.periodo_escolar or '__________'
    grado_promovido = _frase_grado(constancia.promovido_al_grado)

    # 1. Título centrado
    p_titulo = doc.add_paragraph()
    p_titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_titulo.paragraph_format.space_before = Pt(6)
    p_titulo.paragraph_format.space_after = Pt(14)
    p_titulo.paragraph_format.line_spacing = 1.15

    r_t1 = p_titulo.add_run('CONSTANCIA DE PROSECUCIÓN\n')
    r_t1.font.name = 'Arial'
    r_t1.font.size = Pt(13)
    r_t1.font.bold = True

    r_t2 = p_titulo.add_run('EN EL NIVEL DE EDUCACIÓN PRIMARIA')
    r_t2.font.name = 'Arial'
    r_t2.font.size = Pt(13)
    r_t2.font.bold = True

    # 2. Párrafo principal justificado (interlineado 1.5, campos en negrita y subrayados)
    p_cuerpo = doc.add_paragraph()
    p_cuerpo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_cuerpo.paragraph_format.line_spacing = 1.5
    p_cuerpo.paragraph_format.space_after = Pt(12)

    def add_run(p, text, bold=False, underline=False):
        r = p.add_run(text)
        r.font.name = 'Arial'
        r.font.size = Pt(11)
        if bold:
            r.font.bold = True
        if underline:
            r.font.underline = True
        return r

    add_run(p_cuerpo, "Quien suscribe ")
    add_run(p_cuerpo, datos_inst['director_institucion_nombre'], bold=True, underline=True)
    add_run(p_cuerpo, " titular de la Cédula de Identidad Nº V.- ")
    add_run(p_cuerpo, datos_inst['director_institucion_cedula'], bold=True, underline=True)
    add_run(p_cuerpo, " Director(a) de la Institución Educativa ")
    add_run(p_cuerpo, datos_inst['nombre_institucion'], bold=True, underline=True)
    add_run(p_cuerpo, ", ubicada en el Municipio ")
    add_run(p_cuerpo, datos_inst['municipio'], bold=True, underline=True)
    add_run(p_cuerpo, " de la Parroquia ")
    add_run(p_cuerpo, datos_inst['parroquia'], bold=True, underline=True)
    add_run(p_cuerpo, " adscrita al Centro de Desarrollo de la Calidad Educativa Estadal ")
    add_run(p_cuerpo, datos_inst['cdce_estadal'], bold=True, underline=True)
    add_run(p_cuerpo, ". Por la presente hace constar que el (la) estudiante ")
    add_run(p_cuerpo, nombre_alumno, bold=True, underline=True)
    add_run(p_cuerpo, ", titular de la Cédula Escolar Nº Cédula de Identidad Nº o Pasaporte Nº ")
    add_run(p_cuerpo, cedula_alumno, bold=True, underline=True)
    add_run(p_cuerpo, ", nacido (a) en el Municipio ")
    add_run(p_cuerpo, municipio_nac, bold=True, underline=True)
    add_run(p_cuerpo, " del Estado ")
    add_run(p_cuerpo, estado_nac, bold=True, underline=True)
    add_run(p_cuerpo, ", en fecha ")
    add_run(p_cuerpo, fecha_nac_str, bold=True, underline=True)
    add_run(p_cuerpo, ", cursó el ")
    add_run(p_cuerpo, grado_cursado, bold=True, underline=True)
    add_run(p_cuerpo, " Grado, correspondiéndole el literal ")
    add_run(p_cuerpo, literal, bold=True, underline=True)
    add_run(p_cuerpo, " durante el periodo escolar ")
    add_run(p_cuerpo, periodo_escolar, bold=True, underline=True)
    add_run(p_cuerpo, ", ")
    add_run(
        p_cuerpo,
        f"siendo promovido (a) al {grado_promovido} Grado del Nivel de Educación Primaria",
        bold=True,
    )
    add_run(p_cuerpo, ", previo cumplimiento de los requisitos establecidos en la normativa legal vigente.")

    # 3. Párrafo de expedición (alineado a la izquierda, interlineado 1.5)
    p_expedicion = doc.add_paragraph()
    p_expedicion.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_expedicion.paragraph_format.line_spacing = 1.5
    p_expedicion.paragraph_format.space_before = Pt(8)
    p_expedicion.paragraph_format.space_after = Pt(24)

    lugar_exp = constancia.lugar_expedicion or datos_inst['municipio'] or '__________'
    fecha_exp = constancia.fecha_expedicion or timezone.localdate()

    add_run(p_expedicion, "Constancia que se expide en ")
    add_run(p_expedicion, lugar_exp, bold=True, underline=True)
    add_run(p_expedicion, ", a los ")
    add_run(p_expedicion, str(fecha_exp.day), bold=True, underline=True)
    add_run(p_expedicion, " días del mes de ")
    add_run(p_expedicion, MESES[fecha_exp.month - 1], bold=True, underline=True)
    add_run(p_expedicion, " de ")
    add_run(p_expedicion, str(fecha_exp.year), bold=True, underline=True)
    add_run(p_expedicion, ".")

    # 4. Tabla de firmas (2 columnas iguales con bordes finos negros, altura para firma y sello)
    table = doc.add_table(rows=5, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    # Bordes negros finos a la tabla
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        '<w:tblBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '  <w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '  <w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '  <w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '  <w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '</w:tblBorders>'
    )
    tblPr.append(borders)

    # Ancho de columnas: ~8.7 cm cada una (ancho total disponible ~17.59 cm)
    col_width = Cm(8.79)
    for row in table.rows:
        for cell in row.cells:
            cell.width = col_width

    # Contenido de las celdas
    filas_contenido = [
        # Fila 1: Encabezados en negrita centrados
        [
            ("INSTITUCIÓN EDUCATIVA", True, WD_ALIGN_PARAGRAPH.CENTER),
            ("CENTRO DE DESARROLLO DE LA CALIDAD EDUCATIVA ESTADAL", True, WD_ALIGN_PARAGRAPH.CENTER),
        ],
        # Fila 2: Rol
        [
            ("DIRECTOR(A)", False, WD_ALIGN_PARAGRAPH.LEFT),
            ("DIRECTOR(A)", False, WD_ALIGN_PARAGRAPH.LEFT),
        ],
        # Fila 3: Nombre y Apellido
        [
            (f"Nombre y Apellido: {datos_inst['director_institucion_nombre']}", False, WD_ALIGN_PARAGRAPH.LEFT),
            (f"Nombre y Apellido: {datos_inst['director_cdce_nombre']}", False, WD_ALIGN_PARAGRAPH.LEFT),
        ],
        # Fila 4: Cédula
        [
            (f"Número de C.I: {datos_inst['director_institucion_cedula']}", False, WD_ALIGN_PARAGRAPH.LEFT),
            (f"Número de C.I: {datos_inst['director_cdce_cedula']}", False, WD_ALIGN_PARAGRAPH.LEFT),
        ],
        # Fila 5: Firma y Sello
        [
            ("Firma y Sello:", False, WD_ALIGN_PARAGRAPH.LEFT),
            ("Firma y Sello:", False, WD_ALIGN_PARAGRAPH.LEFT),
        ],
    ]

    for idx, fila in enumerate(filas_contenido):
        row = table.rows[idx]
        for col_idx, (texto, es_negrita, alineacion) in enumerate(fila):
            cell = row.cells[col_idx]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            p = cell.paragraphs[0]
            p.alignment = alineacion
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1.15
            run = p.add_run(texto)
            run.font.name = 'Arial'
            run.font.size = Pt(9.5)
            if es_negrita:
                run.font.bold = True

    # Altura mínima para la fila de firma y sello: 2.2 cm
    table.rows[4].height = Cm(2.2)


def generar_docx_constancia_prosecucion(
    alumno: Alumnos,
    constancia: ConstanciaProsecucionFinal,
) -> io.BytesIO:
    """
    Genera una constancia individual en Word (.docx).
    Retorna un buffer io.BytesIO listo para enviar como FileResponse.
    """
    doc = docx.Document()
    _configurar_seccion(doc.sections[0])
    _agregar_encabezado(doc)
    _agregar_cuerpo_constancia(doc, alumno, constancia)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def generar_docx_constancias_lote(
    constancias_queryset,
) -> Tuple[io.BytesIO, str]:
    """
    Genera un único documento Word (.docx) con todas las constancias del lote,
    insertando un salto de página después de cada estudiante.
    Retorna (io.BytesIO, filename).
    """
    doc = docx.Document()
    _configurar_seccion(doc.sections[0])

    constancias = list(constancias_queryset.select_related('alumno'))
    total = len(constancias)

    for idx, constancia in enumerate(constancias):
        alumno = constancia.alumno
        _agregar_encabezado(doc)
        _agregar_cuerpo_constancia(doc, alumno, constancia)

        # Salto de página entre constancias (excepto en la última)
        if idx < total - 1:
            doc.add_page_break()

    grado_nombre = 'Lote'
    seccion_nombre = 'General'
    if constancias:
        primera = constancias[0]
        if primera.grado_cursado:
            grado_nombre = get_valid_filename(primera.grado_cursado.replace(' ', '_'))
        # Intentar obtener grado y sección de inscripciones
        try:
            inscripcion = primera.alumno.inscripciones.select_related('grupo__grado', 'grupo__seccion').first()
            if inscripcion and inscripcion.grupo:
                grado_nombre = get_valid_filename(inscripcion.grupo.grado.nombre_grado.replace(' ', '_'))
                seccion_nombre = get_valid_filename(inscripcion.grupo.seccion.nombre_seccion.replace(' ', '_'))
        except Exception:
            pass

    filename = f"Constancias_Prosecucion_{grado_nombre}_{seccion_nombre}.docx"
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer, filename
