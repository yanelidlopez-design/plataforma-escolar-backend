"""
Generador oficial de Constancia de Prosecución en el Nivel de Educación Primaria
en formato Word (.docx), según especificaciones y estructura del Ministerio
del Poder Popular para la Educación (Venezuela).

IMPORTANTE: Si el usuario dispone de los archivos PNG oficiales exactos, puede
reemplazarlos directamente en backend/static/img/:
  - membrete_mppe.png   (logo institucional con bandera de Venezuela)
  - escudo_estado.png   (escudo/emblema del estado)
  - franja_inferior.png (banner tricolor para el pie de página)

El generador los tomará automáticamente si existen; si no, usa los placeholder
generados con Pillow al importar el módulo.
"""
import io
import logging
from typing import Optional, Tuple
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.text import get_valid_filename

import docx
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml
from docx.oxml.ns import qn

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

# ---------------------------------------------------------------------------
# Rutas de imágenes oficiales (placeholder generado si faltan)
# ---------------------------------------------------------------------------
_STATIC_IMG_DIR = Path(settings.BASE_DIR) / 'backend' / 'static' / 'img'
_MEMBRETE_PATH = _STATIC_IMG_DIR / 'membrete_mppe.png'
_ESCUDO_PATH = _STATIC_IMG_DIR / 'escudo_estado.png'
_FRANJA_PATH = _STATIC_IMG_DIR / 'franja_inferior.png'


def _garantizar_imagenes_placeholder():
    """
    Crea imágenes placeholder con Pillow si aún no existen en backend/static/img/.
    Esto permite que el documento se genere inmediatamente aunque el usuario
    no haya subido los PNG oficiales. Cuando los reemplace, se usarán automáticamente.
    """
    _STATIC_IMG_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.debug('Pillow no disponible; no se generarán placeholders de imagen.')
        return

    AMARILLO = (255, 223, 0)
    AZUL = (0, 55, 153)
    ROJO = (206, 17, 38)
    BLANCO = (255, 255, 255)

    def _fuente(tamano, negrita=False):
        rutas = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf' % ('-Bold' if negrita else ''),
            '/usr/share/fonts/truetype/liberation/Liberation%sSans%s.ttf' % ('' if negrita else '', ''),
            '/usr/share/fonts/truetype/freefont/FreeSans%s.ttf' % ('Bold' if negrita else ''),
        ]
        for ruta in rutas:
            try:
                return ImageFont.truetype(ruta, tamano)
            except Exception:
                continue
        return ImageFont.load_default()

    import math

    # 1. membrete_mppe.png
    if not _MEMBRETE_PATH.is_file():
        w, h = 1200, 400
        img = Image.new('RGB', (w, h), BLANCO)
        draw = ImageDraw.Draw(img)
        tercio = h // 3
        draw.rectangle([0, 0, w, tercio], fill=AMARILLO)
        draw.rectangle([0, tercio, w, 2 * tercio], fill=AZUL)
        draw.rectangle([0, 2 * tercio, w, h], fill=ROJO)

        cx, cy = w // 2, tercio + tercio // 2
        radio_arco = 110
        for i in range(8):
            angulo = math.radians(180 - (i * 20))
            sx = int(cx + radio_arco * math.cos(angulo))
            sy = int(cy + radio_arco * math.sin(angulo) * 0.6)
            r_estrella = 14
            draw.ellipse([sx - r_estrella, sy - r_estrella, sx + r_estrella, sy + r_estrella], fill=BLANCO)

        f_titulo = _fuente(40, negrita=True)
        f_sub = _fuente(28)
        texto1 = 'REPÚBLICA BOLIVARIANA DE VENEZUELA'
        texto2 = 'Ministerio del Poder Popular para la EDUCACIÓN'
        y_texto = tercio + 30

        overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        ovd = ImageDraw.Draw(overlay)
        ovd.rectangle([0, y_texto - 15, w, y_texto + 100], fill=(0, 55, 153, 160))
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(img)

        b1 = draw.textbbox((0, 0), texto1, font=f_titulo)
        b2 = draw.textbbox((0, 0), texto2, font=f_sub)
        w1 = b1[2] - b1[0]
        w2 = b2[2] - b2[0]
        draw.text(((w - w1) // 2, y_texto), texto1, font=f_titulo, fill=BLANCO)
        draw.text(((w - w2) // 2, y_texto + 55), texto2, font=f_sub, fill=BLANCO)
        img.save(_MEMBRETE_PATH, dpi=(300, 300))

    # 2. escudo_estado.png
    if not _ESCUDO_PATH.is_file():
        w2, h2 = 400, 400
        escudo = Image.new('RGB', (w2, h2), BLANCO)
        d = ImageDraw.Draw(escudo)
        d.ellipse([20, 20, w2 - 20, h2 - 20], outline=AZUL, width=8)
        d.ellipse([45, 45, w2 - 45, h2 - 45], outline=AMARILLO, width=4)
        f = _fuente(24, negrita=True)
        txt = 'ESCUDO\nESTADAL'
        bbox = d.textbbox((0, 0), txt, font=f)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        d.text(((w2 - tw) // 2, (h2 - th) // 2), txt, font=f, fill=AZUL, align='center')
        escudo.save(_ESCUDO_PATH, dpi=(300, 300))

    # 3. franja_inferior.png
    if not _FRANJA_PATH.is_file():
        w3, h3 = 1200, 180
        franja = Image.new('RGB', (w3, h3), BLANCO)
        df = ImageDraw.Draw(franja)
        tercio3 = h3 // 3
        df.rectangle([0, 0, w3, tercio3], fill=AMARILLO)
        df.rectangle([0, tercio3, w3, 2 * tercio3], fill=AZUL)
        df.rectangle([0, 2 * tercio3, w3, h3], fill=ROJO)

        cy3 = tercio3 + tercio3 // 2
        radio3 = 60
        for i in range(8):
            angulo = math.radians(180 - (i * 20))
            sx = int(w3 // 2 + radio3 * math.cos(angulo))
            sy = int(cy3 + radio3 * math.sin(angulo) * 0.6)
            r3 = 10
            df.ellipse([sx - r3, sy - r3, sx + r3, sy + r3], fill=BLANCO)
        franja.save(_FRANJA_PATH, dpi=(300, 300))


# Generar placeholders al importar el módulo (una sola vez)
_garantizar_imagenes_placeholder()


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


def _titulo_case(texto: Optional[str]) -> str:
    """Aplica .title() a nombres de personas, instituciones, municipios,
    parroquias y estados. Devuelve '__________' si está vacío."""
    if not texto:
        return '_______________________'
    return str(texto).strip().title()


def _datos_institucionales():
    """Recupera la configuración institucional singleton con normalización .title()."""
    try:
        config = ConfiguracionInstitucional.get_solo()
    except Exception:
        logger.debug('Error obteniendo ConfiguracionInstitucional', exc_info=True)
        config = None

    if config:
        return {
            'nombre_institucion': _titulo_case(config.nombre_institucion) or '_______________________',
            'municipio': _titulo_case(config.municipio) or '_______________________',
            'parroquia': _titulo_case(config.parroquia) or '_______________________',
            'cdce_estadal': _titulo_case(config.cdce_estadal) or '_______________________',
            'director_institucion_nombre': _titulo_case(config.director_institucion_nombre) or '_______________________',
            'director_institucion_cedula': (config.director_institucion_cedula or '__________').upper(),
            'director_cdce_nombre': _titulo_case(config.director_cdce_nombre) or '_______________________',
            'director_cdce_cedula': (config.director_cdce_cedula or '__________').upper(),
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

def _configurar_cabecera_pie_pagina(section):
    """
    Configura el encabezado (section.header) y el pie de página (section.footer)
    de la sección de Word para que aparezcan en todas las páginas.

    Encabezado:
      - membrete_mppe.png alineado a la izquierda
      - escudo_estado.png centrado debajo

    Pie de página:
      - franja_inferior.png a lo ancho completo de la página
    """
    # ---------- Encabezado ----------
    header = section.header
    header.is_linked_to_previous = False

    for p in list(header.paragraphs):
        p._element.getparent().remove(p._element)

    p_logo = header.add_paragraph()
    p_logo.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_logo.paragraph_format.space_before = Pt(0)
    p_logo.paragraph_format.space_after = Pt(2)

    if _MEMBRETE_PATH.is_file():
        try:
            p_logo.add_run().add_picture(str(_MEMBRETE_PATH), width=Inches(2.6))
        except Exception as e:
            logger.debug('No se pudo insertar membrete_mppe.png en header: %s', e)
            r = p_logo.add_run('REPÚBLICA BOLIVARIANA DE VENEZUELA')
            r.font.name = 'Arial'
            r.font.size = Pt(10)
            r.font.bold = True
    else:
        r = p_logo.add_run('REPÚBLICA BOLIVARIANA DE VENEZUELA')
        r.font.name = 'Arial'
        r.font.size = Pt(10)
        r.font.bold = True

    p_escudo = header.add_paragraph()
    p_escudo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_escudo.paragraph_format.space_before = Pt(2)
    p_escudo.paragraph_format.space_after = Pt(4)

    if _ESCUDO_PATH.is_file():
        try:
            p_escudo.add_run().add_picture(str(_ESCUDO_PATH), width=Inches(1.4))
        except Exception as e:
            logger.debug('No se pudo insertar escudo_estado.png en header: %s', e)

    # ---------- Pie de página ----------
    footer = section.footer
    footer.is_linked_to_previous = False

    for p in list(footer.paragraphs):
        p._element.getparent().remove(p._element)

    p_pie = footer.add_paragraph()
    p_pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_pie.paragraph_format.space_before = Pt(2)
    p_pie.paragraph_format.space_after = Pt(0)

    if _FRANJA_PATH.is_file():
        try:
            p_pie.add_run().add_picture(str(_FRANJA_PATH), width=Inches(7.09))
        except Exception as e:
            logger.debug('No se pudo insertar franja_inferior.png en footer: %s', e)

def _agregar_cuerpo_constancia(doc, alumno: Alumnos, constancia: ConstanciaProsecucionFinal):
    """Genera el contenido formal de una constancia de prosecución."""
    datos_inst = _datos_institucionales()

    # Nombre completo del alumno (apellidos y nombres con .title())
    nombre_alumno = ' '.join(
        p for p in [
            alumno.primer_apellido,
            alumno.segundo_apellido,
            alumno.primer_nombre,
            alumno.segundo_nombre,
        ] if p
    ).strip()
    nombre_alumno = _titulo_case(nombre_alumno) if nombre_alumno else '________________________________'

    # Documento de identidad del alumno (cedulas/literales en mayúsculas)
    cedula_alumno = (alumno.cedula_escolar or alumno.numero_documento_identidad or '__________').upper()

    # Municipio y Estado de nacimiento (.title())
    municipio_nac = _titulo_case(alumno.municipio_nacimiento or alumno.lugar_nacimiento)
    estado_nac = _titulo_case(alumno.entidad_federal_nacimiento)

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
    literal = (constancia.literal_final or '____').upper()
    periodo_escolar = constancia.periodo_escolar or '__________'
    grado_promovido = _frase_grado(constancia.promovido_al_grado)

    # 1. Título centrado (dos líneas separadas, negrita Arial 13pt)
    p_linea1 = doc.add_paragraph()
    p_linea1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_linea1.paragraph_format.space_before = Pt(0)
    p_linea1.paragraph_format.space_after = Pt(0)
    p_linea1.paragraph_format.line_spacing = 1.0

    r_t1 = p_linea1.add_run('CONSTANCIA DE PROSECUCIÓN')
    r_t1.font.name = 'Arial'
    r_t1.font.size = Pt(13)
    r_t1.font.bold = True

    p_linea2 = doc.add_paragraph()
    p_linea2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_linea2.paragraph_format.space_before = Pt(0)
    p_linea2.paragraph_format.space_after = Pt(12)
    p_linea2.paragraph_format.line_spacing = 1.0

    r_t2 = p_linea2.add_run('EN EL NIVEL DE EDUCACIÓN PRIMARIA')
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

    lugar_exp = _titulo_case(constancia.lugar_expedicion) or _titulo_case(datos_inst['municipio']) or '__________'
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

    col_width = Cm(8.79)
    for row in table.rows:
        for cell in row.cells:
            cell.width = col_width

    filas_contenido = [
        [
            ("INSTITUCIÓN EDUCATIVA", True, WD_ALIGN_PARAGRAPH.CENTER),
            ("CENTRO DE DESARROLLO DE LA CALIDAD EDUCATIVA ESTADAL", True, WD_ALIGN_PARAGRAPH.CENTER),
        ],
        [
            ("DIRECTOR(A)", False, WD_ALIGN_PARAGRAPH.LEFT),
            ("DIRECTOR(A)", False, WD_ALIGN_PARAGRAPH.LEFT),
        ],
        [
            (f"Nombre y Apellido: {datos_inst['director_institucion_nombre']}", False, WD_ALIGN_PARAGRAPH.LEFT),
            (f"Nombre y Apellido: {datos_inst['director_cdce_nombre']}", False, WD_ALIGN_PARAGRAPH.LEFT),
        ],
        [
            (f"Número de C.I: {datos_inst['director_institucion_cedula']}", False, WD_ALIGN_PARAGRAPH.LEFT),
            (f"Número de C.I: {datos_inst['director_cdce_cedula']}", False, WD_ALIGN_PARAGRAPH.LEFT),
        ],
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

    table.rows[4].height = Cm(2.5)


def _configurar_documento_base(doc):
    """Configura sección, cabecera y pie de página de un documento Word."""
    _configurar_seccion(doc.sections[0])
    _configurar_cabecera_pie_pagina(doc.sections[0])


def generar_docx_constancia_prosecucion(
    alumno: Alumnos,
    constancia: ConstanciaProsecucionFinal,
) -> io.BytesIO:
    """
    Genera una constancia individual en Word (.docx).
    Retorna un buffer io.BytesIO listo para enviar como FileResponse.
    """
    doc = docx.Document()
    _configurar_documento_base(doc)
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
    _configurar_documento_base(doc)

    constancias = list(constancias_queryset.select_related('alumno'))
    total = len(constancias)

    for idx, constancia in enumerate(constancias):
        alumno = constancia.alumno
        _agregar_cuerpo_constancia(doc, alumno, constancia)

        if idx < total - 1:
            doc.add_page_break()

    grado_nombre = 'Lote'
    seccion_nombre = 'General'
    if constancias:
        primera = constancias[0]
        if primera.grado_cursado:
            grado_nombre = get_valid_filename(primera.grado_cursado.replace(' ', '_'))
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
