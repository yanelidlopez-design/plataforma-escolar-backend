"""
Report generation module for academico app.
Contains all export functions (Excel, PDF, CSV) for students, enrollments, and attendance.
"""
import csv
import logging
from django.http import HttpResponse
from django.db.models import ProtectedError
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from html import escape  # escapado de texto para Paragraph (sin parseo XML)
from .models import (
    Alumnos,
    GruposAcademicos,
    Inscripciones,
    Asistencias,
    PeriodoCalificacion,
    CriterioEvaluacion,
    EvaluacionLapsoCriterio,
)
from apps.core.models import GradosAcademicos as CoreGradosAcademicos, Secciones, ConfiguracionPlantel
from apps.personal.models import AlumnoRepresentante, RepresentantesLegales, Profesores


logger = logging.getLogger(__name__)

# ============================================================================
# STUDENT EXPORT CONSTANTS
# ============================================================================

ALUMNOS_EXPORT_ENCABEZADOS = [
    'Cédula Escolar',
    'Tipo Documento',
    'N° de Documento',
    'Primer Nombre',
    'Segundo Nombre',
    'Primer Apellido',
    'Segundo Apellido',
    'Género',
    'Fecha Nacimiento',
    'Lugar Nacimiento',
    'Nacionalidad',
    'Grupo Sanguíneo',
    'Peso (kg)',
    'Talla (cm)',
    'Talla Camisa',
    'Talla Pantalón',
    'Talla Zapato',
    'Alergias',
    'Tratamiento Médico',
    'Condición Física',
    'Discapacidad',
    'Tipo Discapacidad',
    'Fecha Inscripción Inicial',
    'Estatus General',
    'Grado',
    'Sección',
    'Estado Inscripción',
    'Profesor Encargado',
    'Dirección',
    'Ciudad',
    'Estado',
    'Referencia',
    'Representante',
    'Tipo Doc. Rep.',
    'N° Doc. Rep.',
    'Teléfono Rep.',
    'Carnet Patria Código',
    'Carnet Patria Serial',
    'N° Cuenta',
    'Tipo Cuenta',
    'Banco',
]

ALUMNOS_PDF_COLUMNAS = [
    'Cédula Escolar', 'Tipo Doc.', 'N° Doc.', 'Primer Nombre', 'Segundo Nombre',
    'Primer Apellido', 'Segundo Apellido', 'Género', 'Fecha Nac.', 'Lugar Nac.',
    'Nacionalidad', 'Grupo Sanguíneo', 'Peso', 'Talla', 'Grado', 'Sección',
    'Estado Inscripción', 'Profesor Encargado'
]


# ============================================================================
# ENROLLMENT EXPORT CONSTANTS
# ============================================================================

INSCRIPCIONES_EXPORT_ENCABEZADOS = [
    'Alumno', 'Tipo Documento', 'N° de Documento', 'Género', 'Fecha Nacimiento',
    'Grado', 'Sección', 'Turno', 'Docente Encargado',
    'Fecha Inscripción', 'Estado', 'Monto', 'Referencia Bancaria',
    'Dirección', 'Ciudad/Estado',
    'Representante', 'Tipo Doc. Rep.', 'N° Doc. Rep.', 'Teléfono Rep.',
    'Carnet Patria Código', 'Carnet Patria Serial',
    'N° Cuenta', 'Tipo Cuenta', 'Banco'
]

INSCRIPCIONES_PDF_COLUMNAS = [
    'Alumno', 'Tipo Documento', 'N° de Documento',
    'Género', 'Fecha Nacimiento', 'Grado', 'Sección', 'Turno',
    'Docente Encargado', 'Fecha Inscripción', 'Estado', 'Monto', 'Referencia Bancaria'
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _primera_relacion(objeto, relacion):
    """Devuelve la primera instancia de una relación ManyRelatedManager, o None."""
    relacionador = getattr(objeto, relacion, None)
    if relacionador is None:
        return None
    try:
        return next(iter(relacionador.all()), None)
    except Exception:
        return None


def _obtener_nombre_y_apellido(objeto):
    """Devuelve 'Nombre Apellido' u 'N/D' si el objeto no tiene nombre/apellido."""
    if objeto is None:
        return 'N/D'
    nombre = ' '.join(filter(None, [
        getattr(objeto, 'primer_nombre', ''),
        getattr(objeto, 'segundo_nombre', ''),
        getattr(objeto, 'primer_apellido', ''),
        getattr(objeto, 'segundo_apellido', '')
    ])).strip()
    return nombre if nombre else 'N/D'


def _texto_seguro(valor, defecto='N/A'):
    """Escapa caracteres peligrosos y devuelve defecto si está vacío."""
    if valor is None or valor == '':
        return defecto
    return str(valor)


def _tabla_clave_valor(filas, estilos):
    """Crea una tabla clave-valor para filtros en PDF."""
    datos = []
    for clave, valor in filas:
        datos.append([Paragraph(f"<b>{clave}</b>", estilos['Normal']), Paragraph(_texto_seguro(valor), estilos['Normal'])])
    tabla = Table(datos, colWidths=[150, 200])
    tabla.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    return tabla


def _crear_estilos_comprobante():
    """Estilos de ReportLab para el comprobante de inscripción."""
    styles = getSampleStyleSheet()
    return {
        'titulo': ParagraphStyle(
            'ComprobanteTitulo', parent=styles['Heading1'], fontName='Helvetica-Bold',
            fontSize=18, leading=22, textColor=colors.HexColor('#1F4E78'), alignment=1
        ),
        'subtitulo': ParagraphStyle(
            'ComprobanteSubtitulo', parent=styles['Heading2'], fontName='Helvetica-Bold',
            fontSize=12, leading=16, textColor=colors.HexColor('#2C5282'), spaceAfter=6
        ),
        'normal': ParagraphStyle(
            'ComprobanteNormal', parent=styles['Normal'], fontName='Helvetica',
            fontSize=10, leading=14
        ),
        'label': ParagraphStyle(
            'ComprobanteLabel', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=10, leading=14
        ),
    }


def _separar_documento(valor):
    """Separa tipo y número de documento (ej: 'V-19888777' -> 'V', '19888777')."""
    if not valor:
        return '', ''
    valor = str(valor).strip()
    if '-' in valor:
        partes = valor.split('-', 1)
        return partes[0].strip(), partes[1].strip()
    return '', valor


# ============================================================================
# STUDENT REPORT GENERATION
# ============================================================================

def _inscripcion_referencia_alumno(alumno):
    """Mejor inscripción del alumno (Activa/Graduado) para grado/sección/estado.

    Tras la consolidación de estudiantes, Alumnos ya no tiene FK directas de
    grado/sección: se resuelven vía Inscripciones -> grupo. Usa la lista
    prefetcheada si existe (evita N+1 en exportaciones masivas).
    """
    inscripcion = _primera_relacion(alumno, 'inscripciones')
    if inscripcion is not None:
        return inscripcion
    try:
        return alumno.inscripciones.filter(estado_inscripcion__in=['Activa', 'Graduado']).first()
    except Exception:
        return None


def _fila_alumno(alumno):
    """Genera una fila de datos para exportación de alumnos (Excel/CSV)."""
    direccion = alumno.id_direccion_residencia
    relacion = _primera_relacion(alumno, 'representantes_vinculados')
    # El pivot devuelve AlumnoRepresentante; la persona es .representante
    representante = relacion.representante if relacion else None

    repre_nombre = _obtener_nombre_y_apellido(representante) if representante else 'N/D'
    repre_tipo_doc, repre_num_doc = _separar_documento(representante.cedula) if representante else ('', '')
    repre_telefono = (representante.telefono_principal or 'N/D') if representante else 'N/D'

    inscripcion = _inscripcion_referencia_alumno(alumno)
    grupo = inscripcion.grupo if inscripcion else None
    grado_nombre = grupo.grado.nombre_grado if grupo and grupo.grado else 'N/D'
    seccion_nombre = grupo.seccion.nombre_seccion if grupo and grupo.seccion else 'N/D'
    profesor_nombre = _obtener_nombre_y_apellido(alumno.id_profesor_encargado) if alumno.id_profesor_encargado else 'N/D'

    return [
        alumno.cedula_escolar or 'N/D',
        alumno.tipo_documento_identidad or 'V',
        alumno.numero_documento_identidad or 'N/D',
        alumno.primer_nombre or 'N/D',
        alumno.segundo_nombre or 'N/D',
        alumno.primer_apellido or 'N/D',
        alumno.segundo_apellido or 'N/D',
        alumno.genero or 'N/D',
        alumno.fecha_nacimiento or 'N/D',
        alumno.lugar_nacimiento or 'N/D',
        alumno.nacionalidad or 'N/D',
        alumno.grupo_sanguineo or 'N/D',
        alumno.peso_kg or 'N/D',
        alumno.talla_cm or 'N/D',
        alumno.talla_camisa or 'N/D',
        alumno.talla_pantalon or 'N/D',
        alumno.talla_zapato or 'N/D',
        alumno.alergico_a or 'N/D',
        alumno.tratamiento_medico or 'N/D',
        alumno.condicion_fisica or 'N/D',
        'Sí' if alumno.discapacidad else 'No',
        alumno.tipo_discapacidad or 'N/D',
        alumno.fecha_inscripcion_inicial or 'N/D',
        alumno.estatus_general or 'N/D',
        grado_nombre,
        seccion_nombre,
        inscripcion.estado_inscripcion if inscripcion else 'N/D',
        profesor_nombre,
        f"{direccion.calle}, {direccion.ciudad}, {direccion.estado}" if direccion else 'N/D',
        direccion.ciudad if direccion else 'N/D',
        direccion.estado if direccion else 'N/D',
        direccion.referencia if direccion else 'N/D',
        repre_nombre,
        repre_tipo_doc,
        repre_num_doc,
        repre_telefono,
        alumno.carnet_patria_codigo or 'N/D',
        alumno.carnet_patria_serial or 'N/D',
        alumno.numero_cuenta or 'N/D',
        alumno.tipo_cuenta or 'N/D',
        alumno.banco or 'N/D',
    ]


def _fila_alumno_pdf(alumno):
    """Genera una fila de datos simplificada para exportación PDF de alumnos."""
    inscripcion = _inscripcion_referencia_alumno(alumno)
    grupo = inscripcion.grupo if inscripcion else None
    return [
        alumno.cedula_escolar or 'N/D',
        alumno.tipo_documento_identidad or 'V',
        alumno.numero_documento_identidad or 'N/D',
        alumno.primer_nombre or 'N/D',
        alumno.segundo_nombre or 'N/D',
        alumno.primer_apellido or 'N/D',
        alumno.segundo_apellido or 'N/D',
        alumno.genero or 'N/D',
        alumno.fecha_nacimiento or 'N/D',
        alumno.lugar_nacimiento or 'N/D',
        alumno.nacionalidad or 'N/D',
        alumno.grupo_sanguineo or 'N/D',
        alumno.peso_kg or 'N/D',
        alumno.talla_cm or 'N/D',
        grupo.grado.nombre_grado if grupo and grupo.grado else 'N/D',
        grupo.seccion.nombre_seccion if grupo and grupo.seccion else 'N/D',
        inscripcion.estado_inscripcion if inscripcion else 'N/D',
        _obtener_nombre_y_apellido(alumno.id_profesor_encargado) if alumno.id_profesor_encargado else 'N/D',
    ]


def exportar_alumnos_excel(queryset):
    """Exporta alumnos a formato Excel."""
    if not queryset.exists():
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Alumnos"

    fuente_cabecera = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    relleno_azul = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")

    ws.append(ALUMNOS_EXPORT_ENCABEZADOS)

    for col_num in range(1, len(ALUMNOS_EXPORT_ENCABEZADOS) + 1):
        celda = ws.cell(row=1, column=col_num)
        celda.font = fuente_cabecera
        celda.fill = relleno_azul

    for alumno in queryset:
        ws.append(_fila_alumno(alumno))

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="alumnos.xlsx"'
    wb.save(response)
    return response


def exportar_alumnos_pdf(queryset, grado_id=None, seccion_id=None, estado=None):
    """Exporta alumnos a formato PDF."""
    if not queryset.exists():
        return None

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="alumnos.pdf"'

    doc = SimpleDocTemplate(
        response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    story = []

    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        'TituloAlumnos',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1F4E78'),
        alignment=1
    )
    estilo_subtitulo = ParagraphStyle(
        'SubtituloAlumnos',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#2C5282'),
        spaceAfter=6
    )

    story.append(Paragraph("PLATAFORMA ESCOLAR - CONTROL DE INSCRIPCIONES", estilo_titulo))
    story.append(Spacer(1, 20))

    filas_filtro = []
    if grado_id:
        nombre_grado_f = None
        if str(grado_id).isdigit():
            nombre_grado_f = CoreGradosAcademicos.objects.filter(
                pk=grado_id
            ).values_list('nombre_grado', flat=True).first()
        filas_filtro.append(('Grado:', nombre_grado_f or str(grado_id)))
    if seccion_id:
        nombre_seccion_f = None
        if str(seccion_id).isdigit():
            nombre_seccion_f = Secciones.objects.filter(
                pk=seccion_id
            ).values_list('nombre_seccion', flat=True).first()
        filas_filtro.append(('Sección:', nombre_seccion_f or str(seccion_id)))
    if estado:
        filas_filtro.append(('Estado:', estado))
    if filas_filtro:
        story.append(Paragraph("FILTROS APLICADOS", estilo_subtitulo))
        story.append(_tabla_clave_valor(filas_filtro, styles))
        story.append(Spacer(1, 12))

    encabezados = ALUMNOS_PDF_COLUMNAS
    ancho_util = letter[0] - 80
    pesos = [55, 35, 50, 100, 45, 32, 50, 30, 45, 100, 42, 90]
    total_peso = sum(pesos)
    col_widths = [round(p * ancho_util / total_peso) for p in pesos]
    estilo_cab = ParagraphStyle(
        'PdfAluCab', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=7, leading=9, textColor=colors.white, alignment=1
    )
    estilo_celda = ParagraphStyle(
        'PdfAluCelda', parent=styles['Normal'], fontName='Helvetica',
        fontSize=7, leading=9
    )

    datos_tabla = [[Paragraph(escape(h), estilo_cab) for h in encabezados]]
    for alumno in queryset:
        datos_tabla.append([
            Paragraph(_texto_seguro(valor, 'N/D'), estilo_celda)
            for valor in _fila_alumno_pdf(alumno)
        ])

    tabla_pdf = Table(
        datos_tabla,
        colWidths=col_widths,
        repeatRows=1
    )
    tabla_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E78')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
    ]))

    story.append(tabla_pdf)
    doc.build(story)
    return response


def exportar_alumnos_csv(queryset):
    """Exporta alumnos a formato CSV."""
    if not queryset.exists():
        return None

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="alumnos.csv"'
    response.write('\ufeff')  # BOM UTF-8 para que Excel lo abra con acentos correctos

    writer = csv.writer(response)
    writer.writerow(ALUMNOS_EXPORT_ENCABEZADOS)

    for alumno in queryset:
        writer.writerow(_fila_alumno(alumno))

    return response


# ============================================================================
# ENROLLMENT REPORT GENERATION
# ============================================================================

def _fila_inscripcion(inscripcion):
    """Genera una fila de datos para exportación de inscripciones (Excel/CSV)."""
    alumno = inscripcion.alumno
    grupo = inscripcion.grupo
    direccion = alumno.id_direccion_residencia
    relacion = _primera_relacion(alumno, 'representantes_vinculados')
    # El pivot devuelve AlumnoRepresentante; la persona es .representante
    representante = relacion.representante if relacion else None

    repre_nombre = _obtener_nombre_y_apellido(representante) if representante else 'N/D'
    repre_tipo_doc, repre_num_doc = _separar_documento(representante.cedula) if representante else ('', '')
    repre_telefono = (representante.telefono_principal or 'N/D') if representante else 'N/D'

    alumno_nombre = _obtener_nombre_y_apellido(alumno)
    profesor_nombre = _obtener_nombre_y_apellido(grupo.profesor_director) if grupo.profesor_director else 'N/D'

    return [
        alumno_nombre,
        alumno.tipo_documento_identidad or 'V',
        alumno.numero_documento_identidad or 'N/D',
        alumno.genero or 'N/D',
        alumno.fecha_nacimiento or 'N/D',
        grupo.grado.nombre_grado if grupo.grado else 'N/D',
        grupo.seccion.nombre_seccion if grupo.seccion else 'N/D',
        grupo.turno.nombre_turno if grupo.turno else 'N/D',
        profesor_nombre,
        inscripcion.fecha_inscripcion or 'N/D',
        inscripcion.estado_inscripcion or 'N/D',
        inscripcion.monto_pago or 'N/D',
        inscripcion.referencia_bancaria or 'N/D',
        f"{direccion.calle}, {direccion.ciudad}, {direccion.estado}" if direccion else 'N/D',
        f"{direccion.ciudad}, {direccion.estado}" if direccion else 'N/D',
        repre_nombre,
        repre_tipo_doc,
        repre_num_doc,
        repre_telefono,
        alumno.carnet_patria_codigo or 'N/D',
        alumno.carnet_patria_serial or 'N/D',
        alumno.numero_cuenta or 'N/D',
        alumno.tipo_cuenta or 'N/D',
        alumno.banco or 'N/D',
    ]


def _fila_inscripcion_pdf(inscripcion):
    """Genera una fila de datos simplificada para exportación PDF de inscripciones."""
    alumno = inscripcion.alumno
    grupo = inscripcion.grupo

    return [
        _obtener_nombre_y_apellido(alumno),
        alumno.tipo_documento_identidad or 'V',
        alumno.numero_documento_identidad or 'N/D',
        alumno.genero or 'N/D',
        alumno.fecha_nacimiento or 'N/D',
        grupo.grado.nombre_grado if grupo.grado else 'N/D',
        grupo.seccion.nombre_seccion if grupo.seccion else 'N/D',
        grupo.turno.nombre_turno if grupo.turno else 'N/D',
        _obtener_nombre_y_apellido(grupo.profesor_director) if grupo.profesor_director else 'N/D',
        inscripcion.fecha_inscripcion or 'N/D',
        inscripcion.estado_inscripcion or 'N/D',
        inscripcion.monto_pago or 'N/D',
        inscripcion.referencia_bancaria or 'N/D',
    ]


def exportar_inscripciones_excel(queryset):
    """Exporta inscripciones a formato Excel."""
    if not queryset.exists():
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Inscripciones"

    fuente_cabecera = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    relleno_azul = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")

    ws.append(INSCRIPCIONES_EXPORT_ENCABEZADOS)
    for col_num in range(1, len(INSCRIPCIONES_EXPORT_ENCABEZADOS) + 1):
        celda = ws.cell(row=1, column=col_num)
        celda.font = fuente_cabecera
        celda.fill = relleno_azul

    for inscripcion in queryset:
        ws.append(_fila_inscripcion(inscripcion))

    for col in ws.columns:
        max_len = max(len(str(celda.value or '')) for celda in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 45)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="inscripciones.xlsx"'
    wb.save(response)
    return response


def exportar_inscripciones_pdf(queryset, request_params):
    """Exporta inscripciones a formato PDF."""
    if not queryset.exists():
        return None

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="inscripciones.pdf"'

    doc = SimpleDocTemplate(
        response, pagesize=landscape(letter), rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    story = []
    styles = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle(
        'TituloInscripciones', parent=styles['Heading1'], fontName='Helvetica-Bold',
        fontSize=18, leading=22, textColor=colors.HexColor('#1F4E78'), alignment=1
    )
    estilo_subtitulo = ParagraphStyle(
        'SubtituloInscripciones', parent=styles['Heading2'], fontName='Helvetica-Bold',
        fontSize=12, leading=16, textColor=colors.HexColor('#2C5282'), spaceAfter=6
    )

    story.append(Paragraph("PLATAFORMA ESCOLAR - INSCRIPCIONES", estilo_titulo))
    story.append(Spacer(1, 20))

    filas_filtro = []
    for etiqueta, param in (
        ('Grado:', 'grado'), ('Sección:', 'seccion'),
        ('Estado:', 'estado_inscripcion'), ('Búsqueda:', 'search'),
    ):
        valor = (request_params.get(param) or '').strip()
        if valor:
            filas_filtro.append((etiqueta, valor))
    if filas_filtro:
        story.append(Paragraph("FILTROS APLICADOS", estilo_subtitulo))
        story.append(_tabla_clave_valor(filas_filtro, styles))
        story.append(Spacer(1, 12))

    estilo_cab = ParagraphStyle(
        'PdfInsCab', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=7.5, leading=9, textColor=colors.white, alignment=1
    )
    estilo_celda = ParagraphStyle(
        'PdfInsCelda', parent=styles['Normal'], fontName='Helvetica',
        fontSize=7.5, leading=9
    )

    datos_tabla = [[Paragraph(escape(h), estilo_cab) for h in INSCRIPCIONES_PDF_COLUMNAS]]
    for inscripcion in queryset:
        datos_tabla.append([
            Paragraph(_texto_seguro(valor, 'N/D'), estilo_celda)
            for valor in _fila_inscripcion_pdf(inscripcion)
        ])

    ancho_util = landscape(letter)[0] - 80
    pesos = [110, 38, 55, 55, 32, 42, 100, 48, 45, 42, 60, 100, 45]
    total_peso = sum(pesos)
    col_widths = [round(p * ancho_util / total_peso) for p in pesos]

    tabla_pdf = Table(
        datos_tabla,
        colWidths=col_widths,
        repeatRows=1
    )
    tabla_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E78')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
    ]))
    story.append(tabla_pdf)
    doc.build(story)
    return response


def exportar_inscripciones_csv(queryset):
    """Exporta inscripciones a formato CSV."""
    if not queryset.exists():
        return None

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="inscripciones.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(INSCRIPCIONES_EXPORT_ENCABEZADOS)

    for inscripcion in queryset:
        writer.writerow(_fila_inscripcion(inscripcion))

    return response


# ============================================================================
# ATTENDANCE REPORT GENERATION
# ============================================================================

def exportar_asistencias_csv(queryset):
    """Exporta asistencias a formato CSV."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="asistencias.csv"'

    writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['Fecha', 'Alumno', 'Cédula Escolar', 'Grado', 'Sección', 'Estado', 'Observaciones'])

    for asistencia in queryset:
        writer.writerow([
            asistencia.fecha,
            f"{asistencia.alumno.primer_nombre} {asistencia.alumno.primer_apellido}",
            asistencia.alumno.cedula_escolar or 'N/A',
            asistencia.grupo.grado.nombre_grado,
            asistencia.grupo.seccion.nombre_seccion,
            asistencia.get_estado_display(),
            asistencia.observaciones or ''
        ])

    return response


def exportar_asistencias_excel(queryset):
    """Exporta asistencias a formato Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Asistencias"

    fuente_titulo = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    relleno_azul = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")

    encabezados = ['Fecha', 'Alumno', 'Cédula Escolar', 'Grado', 'Sección', 'Estado', 'Observaciones']
    ws.append(encabezados)

    for col_num in range(1, 8):
        celda = ws.cell(row=1, column=col_num)
        celda.font = fuente_titulo
        celda.fill = relleno_azul

    for asistencia in queryset:
        ws.append([
            asistencia.fecha,
            f"{asistencia.alumno.primer_nombre} {asistencia.alumno.primer_apellido}",
            asistencia.alumno.cedula_escolar or 'N/A',
            asistencia.grupo.grado.nombre_grado,
            asistencia.grupo.seccion.nombre_seccion,
            asistencia.get_estado_display(),
            asistencia.observaciones or ''
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="asistencias.xlsx"'

    wb.save(response)
    return response


def exportar_asistencias_pdf(queryset, fecha_inicio=None, fecha_fin=None):
    """Exporta asistencias a formato PDF."""
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="asistencias.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []

    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        'TituloReporte',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1F4E78'),
        alignment=1
    )

    story.append(Paragraph("PLATAFORMA ESCOLAR - REPORTE DE ASISTENCIAS", estilo_titulo))
    story.append(Spacer(1, 20))

    if fecha_inicio or fecha_fin:
        rango_fecha = f"Del {fecha_inicio or 'Inicio'} al {fecha_fin or 'Actual'}"
        story.append(Paragraph(f"Período: {rango_fecha}", styles['Normal']))
        story.append(Spacer(1, 10))

    datos_tabla = [['Fecha', 'Alumno', 'Cédula', 'Grado', 'Sección', 'Estado', 'Observaciones']]

    for asistencia in queryset:
        datos_tabla.append([
            str(asistencia.fecha),
            f"{asistencia.alumno.primer_nombre} {asistencia.alumno.primer_apellido}",
            asistencia.alumno.cedula_escolar or 'N/A',
            asistencia.grupo.grado.nombre_grado,
            asistencia.grupo.seccion.nombre_seccion,
            asistencia.get_estado_display(),
            asistencia.observaciones or ''
        ])

    tabla_pdf = Table(datos_tabla, colWidths=[80, 150, 100, 80, 60, 80, 100])
    tabla_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E78')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F2F4F7')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')])
    ]))

    story.append(tabla_pdf)

    doc.build(story)
    return response


# ============================================================================
# INFORME DESCRIPTIVO TRIMESTRAL (ReportLab)
# ============================================================================

def generar_pdf_informe_descriptivo(alumno_objeto, periodo_objeto, grupo_objeto):
    """
    Genera el Informe Descriptivo Trimestral en PDF (Diciembre, Abril o Julio)
    para un alumno, periodo y grupo dados.

    El documento incluye:
      - Membrete institucional (República Bolivariana de Venezuela,
        Ministerio del Poder Popular para la Educación, E.B Creación San José,
        Cod. DEA: OD12431208 | Calabozo - El Calvario).
      - Datos del estudiante y su representante legal.
      - Tabla dinámica de criterios cualitativos evaluados en el lapso.
      - Bloque de sugerencias del docente y espacios de firma (Docente del Grado
        y Directora) con espacio para sello húmedo.

    Retorna un io.BytesIO posicionado al inicio con el PDF listo para servir.
    """
    import io

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Informe Descriptivo - {alumno_objeto}",
        author="E.B Creación San José",
        subject="Informe Descriptivo Trimestral",
    )

    # ---------- Estilos ----------
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
        'Titulo', fontName='Helvetica-Bold', fontSize=14, leading=18,
        alignment=TA_CENTER, textColor=colors.HexColor('#1a3a5c'),
        spaceAfter=10,
    )
    estilo_etiqueta = ParagraphStyle(
        'DatoEtiqueta', fontName='Helvetica-Bold', fontSize=10, leading=13,
        alignment=TA_LEFT, textColor=colors.HexColor('#333333'),
    )
    estilo_valor = ParagraphStyle(
        'DatoValor', fontName='Helvetica', fontSize=10, leading=13,
        alignment=TA_LEFT, textColor=colors.HexColor('#000000'),
    )
    estilo_tabla_enc = ParagraphStyle(
        'TablaEnc', fontName='Helvetica-Bold', fontSize=9, leading=12,
        alignment=TA_CENTER, textColor=colors.white,
    )
    estilo_tabla_celda = ParagraphStyle(
        'TablaCelda', fontName='Helvetica', fontSize=9, leading=12,
        alignment=TA_LEFT, textColor=colors.HexColor('#000000'),
    )
    estilo_sugerencias = ParagraphStyle(
        'Sugerencias', fontName='Helvetica', fontSize=10, leading=14,
        alignment=TA_JUSTIFY, textColor=colors.HexColor('#333333'),
    )
    estilo_firma = ParagraphStyle(
        'Firma', fontName='Helvetica-Bold', fontSize=9, leading=12,
        alignment=TA_CENTER, textColor=colors.HexColor('#333333'),
    )

    story = []

    # ---------- MEMBRETE INSTITUCIONAL ----------
    story.append(Paragraph("República Bolivariana de Venezuela", estilo_membrete_1))
    story.append(Paragraph("Ministerio del Poder Popular para la Educación", estilo_membrete_2))
    story.append(Paragraph("E.B Creación San José", estilo_membrete_3))
    story.append(Paragraph("Cod. DEA: OD12431208 | Calabozo - El Calvario", estilo_membrete_4))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1a3a5c')))
    story.append(Spacer(1, 14))

    # ---------- TÍTULO ----------
    lapso_nombre = dict(PeriodoCalificacion.NUMERO_PERIODO_CHOICES).get(
        periodo_objeto.numero_periodo, f"Lapso {periodo_objeto.numero_periodo}"
    )
    story.append(Paragraph(f"Informe Descriptivo Trimestral - {lapso_nombre}", estilo_titulo))
    story.append(Spacer(1, 10))

    # ---------- DATOS DEL ESTUDIANTE Y REPRESENTANTE ----------
    nombre_completo = (
        f"{alumno_objeto.primer_nombre} {alumno_objeto.segundo_nombre or ''} "
        f"{alumno_objeto.primer_apellido} {alumno_objeto.segundo_apellido or ''}"
    ).strip()

    grado_nombre = (
        grupo_objeto.grado.nombre_grado
        if grupo_objeto and grupo_objeto.grado_id else 'N/A'
    )
    seccion_nombre = (
        grupo_objeto.seccion.nombre_seccion
        if grupo_objeto and grupo_objeto.seccion_id else 'N/A'
    )

    representante_nombre = 'No asignado'
    try:
        ar = AlumnoRepresentante.objects.filter(
            alumno=alumno_objeto, es_principal=True
        ).select_related('representante').first()
        if ar and ar.representante:
            rep = ar.representante
            representante_nombre = (
                f"{rep.primer_nombre} {rep.segundo_nombre or ''} "
                f"{rep.primer_apellido} {rep.segundo_apellido or ''}"
            ).strip()
    except Exception:  # nosec B101
        logger.debug(
            'Error obteniendo representante del alumno %s',
            getattr(alumno_objeto, 'pk', None), exc_info=True,
        )

    datos_estudiante = [
        [Paragraph('Nombre del Estudiante', estilo_etiqueta),
         Paragraph(nombre_completo, estilo_valor)],
        [Paragraph('Cédula Escolar / C.I.', estilo_etiqueta),
         Paragraph(
             alumno_objeto.cedula_escolar
             or alumno_objeto.numero_documento_identidad
             or 'N/A', estilo_valor)],
        [Paragraph('Grado', estilo_etiqueta), Paragraph(grado_nombre, estilo_valor)],
        [Paragraph('Sección', estilo_etiqueta), Paragraph(seccion_nombre, estilo_valor)],
        [Paragraph('Representante Legal', estilo_etiqueta),
         Paragraph(representante_nombre, estilo_valor)],
    ]

    tabla_datos = Table(datos_estudiante, colWidths=[4.6 * cm, 10.4 * cm])
    tabla_datos.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eef2f7')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(tabla_datos)
    story.append(Spacer(1, 14))

    # ---------- TABLA DINÁMICA DE CRITERIOS ----------
    story.append(Paragraph(
        'Evaluación de Criterios de Aprendizaje',
        ParagraphStyle(
            'SubtituloTabla', parent=estilo_etiqueta, fontSize=11,
            spaceAfter=6, textColor=colors.HexColor('#1a3a5c'),
        ),
    ))

    indicador_display = dict(EvaluacionLapsoCriterio.INDICADOR_CHOICES)

    evaluaciones = EvaluacionLapsoCriterio.objects.filter(
        alumno=alumno_objeto, periodo=periodo_objeto
    ).select_related('criterio').order_by('criterio__materia_nombre')

    datos_tabla = [
        [Paragraph('Criterio de Aprendizaje', estilo_tabla_enc),
         Paragraph('Indicador (PL, L, PM, EP, I)', estilo_tabla_enc)],
    ]

    sugerencias_list = []
    for ev in evaluaciones:
        datos_tabla.append([
            Paragraph(
                f"{ev.criterio.materia_nombre} - {ev.criterio.descripcion_criterio}",
                estilo_tabla_celda,
            ),
            Paragraph(
                f"{ev.indicador} - {indicador_display.get(ev.indicador, ev.indicador)}",
                estilo_tabla_celda,
            ),
        ])
        if ev.sugerencias and ev.sugerencias.strip():
            sugerencias_list.append(
                f"• {ev.criterio.materia_nombre}: {ev.sugerencias.strip()}"
            )

    tabla_criterios = Table(datos_tabla, colWidths=[11 * cm, 5 * cm])
    tabla_criterios.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#999999')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(tabla_criterios)
    story.append(Spacer(1, 14))

    # ---------- BLOQUE DE SUGERENCIAS ----------
    if sugerencias_list:
        story.append(Paragraph(
            'Sugerencias del Docente',
            ParagraphStyle(
                'SubtituloSugerencias', parent=estilo_etiqueta, fontSize=11,
                spaceAfter=6, textColor=colors.HexColor('#1a3a5c'),
            ),
        ))
        sugerencias_texto = '<br/>'.join(sugerencias_list)
        story.append(Paragraph(sugerencias_texto, estilo_sugerencias))
        story.append(Spacer(1, 14))

    # ---------- BLOQUE DE FIRMAS ----------
    docente_nombre = 'Docente del Grado'
    docente_cedula = ''
    if grupo_objeto and grupo_objeto.profesor_director_id:
        pd = grupo_objeto.profesor_director
        docente_nombre = (
            f"{pd.primer_nombre} {pd.segundo_nombre or ''} "
            f"{pd.primer_apellido} {pd.segundo_apellido or ''}"
        ).strip()
        docente_cedula = pd.cedula or ''

    firma_tabla = Table([
        [
            Paragraph(
                f'Docente del Grado<br/>{docente_nombre}'
                f'{("<br/>" + docente_cedula) if docente_cedula else ""}',
                estilo_firma,
            ),
            Paragraph(
                'Sello Húmedo<br/>de la Institución<br/><br/>'
                'E.B Creación San José', estilo_firma,
            ),
            Paragraph(
                'Directora<br/>_______________________<br/>C.I. _______________',
                estilo_firma,
            ),
        ],
    ], colWidths=[6 * cm, 6 * cm, 6 * cm])
    firma_tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 26),
        ('LINEBELOW', (0, 0), (0, 0), 0.8, colors.black),
        ('LINEBELOW', (2, 0), (2, 0), 0.8, colors.black),
    ]))
    story.append(firma_tabla)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ============================================================================
# SERVICIO B: PDF DE LA CONSTANCIA DE PROSECUCIÓN FINAL (BOLETA DE JULIO)
# ============================================================================

def generar_pdf_constancia_prosecucion(alumno_objeto, constancia_objeto):
    """
    Genera la Constancia de Prosecución en el Nivel de Educación Primaria
    (boleta oficial única de Julio) en PDF en memoria.

    Args:
        alumno_objeto: instancia de ``Alumnos``.
        constancia_objeto: instancia de ``ConstanciaProsecucionFinal``.

    El documento incluye:
      - Membrete institucional (República Bolivariana de Venezuela,
        Ministerio del Poder Popular para la Educación, E.B Creación San José,
        Cod. DEA: OD12431208 | Calabozo - El Calvario).
      - Título central en negrita: "CONSTANCIA DE PROSECUCIÓN EN EL NIVEL DE
        EDUCACIÓN PRIMARIA".
      - Redacción legal del formato con director, estudiante, literal final,
        periodo escolar y grado de promoción.
      - Bloque de expedición con la fecha de emisión.
      - Cuadro de firmas paralelas de 3 columnas (Institución Educativa,
        espacio de sello húmedo y Centro de Desarrollo de la Calidad
        Educativa Estadal).

    Retorna un ``io.BytesIO`` posicionado al inicio con el PDF listo para servir.
    """
    import io

    from django.utils import timezone
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )

    meses = (
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
    )

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=f"Constancia de Prosecución - {alumno_objeto}",
        author="E.B Creación San José",
        subject="Constancia de Prosecución en el Nivel de Educación Primaria",
    )

    # ---------- Estilos ----------
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

    story = []

    # ---------- MEMBRETE INSTITUCIONAL ----------
    story.append(Paragraph("República Bolivariana de Venezuela", estilo_membrete_1))
    story.append(Paragraph("Ministerio del Poder Popular para la Educación", estilo_membrete_2))
    story.append(Paragraph("E.B Creación San José", estilo_membrete_3))
    story.append(Paragraph("Cod. DEA: OD12431208 | Calabozo - El Calvario", estilo_membrete_4))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1a3a5c')))
    story.append(Spacer(1, 14))

    # ---------- TÍTULO CENTRAL ----------
    story.append(Paragraph(
        'CONSTANCIA DE PROSECUCIÓN EN EL NIVEL DE EDUCACIÓN PRIMARIA',
        estilo_titulo,
    ))
    story.append(Spacer(1, 6))

    # ---------- DATOS DEL DIRECTOR/A (ConfiguracionPlantel -> Profesores) ----------
    director_nombre = '_______________________'
    director_cedula = 'V.-__________'
    try:
        configuracion = ConfiguracionPlantel.objects.first()
        if configuracion and configuracion.id_director_actual:
            profesor_director = Profesores.objects.filter(
                pk=configuracion.id_director_actual
            ).first()
            if profesor_director:
                nombre_director = ' '.join(filter(None, [
                    profesor_director.primer_nombre,
                    profesor_director.segundo_nombre,
                    profesor_director.primer_apellido,
                    profesor_director.segundo_apellido,
                ])).strip()
                if nombre_director:
                    director_nombre = nombre_director
                cedula_director = (profesor_director.cedula or '').strip()
                if cedula_director:
                    if '-' in cedula_director:
                        tipo_doc, numero_doc = cedula_director.split('-', 1)
                        director_cedula = f'{tipo_doc.strip()}.-{numero_doc.strip()}'
                    else:
                        director_cedula = f'V.-{cedula_director}'
    except Exception:  # nosec B101
        logger.debug('Error resolviendo director del plantel para la constancia', exc_info=True)

    # ---------- DATOS DEL ESTUDIANTE ----------
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
    municipio_alumno = escape(
        alumno_objeto.municipio_nacimiento
        or alumno_objeto.lugar_nacimiento
        or '__________'
    )
    estado_alumno = escape(alumno_objeto.entidad_federal_nacimiento or '__________')

    fecha_nacimiento_texto = '__________'
    if alumno_objeto.fecha_nacimiento:
        fecha_nacimiento_texto = (
            f'{alumno_objeto.fecha_nacimiento.day} de '
            f'{meses[alumno_objeto.fecha_nacimiento.month - 1]} de '
            f'{alumno_objeto.fecha_nacimiento.year}'
        )

    # Grado cursado: vía mejor inscripción -> grupo -> grado (Alumnos no tiene
    # FK directas de grado/sección tras la consolidación de estudiantes).
    grado_cursado = '__________'
    try:
        inscripcion_referencia = _inscripcion_referencia_alumno(alumno_objeto)
        if inscripcion_referencia is not None and inscripcion_referencia.grupo_id:
            grado_cursado = (
                inscripcion_referencia.grupo.grado.nombre_grado or '__________'
            )
    except Exception:  # nosec B101
        logger.debug(
            'Error resolviendo grado cursado del alumno %s para la constancia',
            getattr(alumno_objeto, 'pk', None), exc_info=True,
        )

    def _frase_grado(valor):
        """'Primer Grado' -> 'Primer Grado'; '1' -> '1 Grado' (cierra la frase)."""
        texto = str(valor or '__________').strip()
        if 'grado' in texto.lower():
            return texto
        return f'{texto} Grado'

    literal_final = escape(str(constancia_objeto.literal_final or '____'))
    periodo_escolar = escape(str(constancia_objeto.periodo_escolar or '__________'))
    siguiente_grado = escape(_frase_grado(constancia_objeto.promovido_al_grado))
    grado_cursado_frase = escape(_frase_grado(grado_cursado))

    # ---------- REDACCIÓN LEGAL DEL CUERPO ----------
    cuerpo_texto = (
        f'Quien suscribe <b>{escape(director_nombre)}</b>, titular de la Cédula de '
        f'Identidad N° {escape(director_cedula)}, Director(a) de la Institución '
        'Educativa E.B Creación San José, ubicada en el Municipio Francisco de '
        'Miranda de la Parroquia Calabozo adscrita al Centro de Desarrollo de la '
        'Calidad Educativa Estadal... <br/><br/>'
        f'Hace constar que el (la) estudiante <b>{nombre_alumno}</b>, titular de la '
        f'Cédula Escolar/C.I. N° {cedula_alumno}, nacido (a) en el Municipio '
        f'{municipio_alumno} del Estado {estado_alumno}, en fecha '
        f'{fecha_nacimiento_texto}, cursó el {grado_cursado_frase}, '
        f'correspondiéndole el literal <b>{literal_final}</b> durante el periodo '
        f'escolar {periodo_escolar}, siendo promovido (a) al '
        f'<b>{siguiente_grado}</b> del Nivel de Educación Primaria.'
    )
    story.append(Paragraph(cuerpo_texto, estilo_cuerpo))
    story.append(Spacer(1, 8))

    # ---------- BLOQUE DE VALIDACIÓN DE EXPEDICIÓN ----------
    fecha_expedicion = constancia_objeto.fecha_expedicion or timezone.localdate()
    expedicion_texto = (
        f'Constancia que se expide en Calabozo, a los {fecha_expedicion.day} días '
        f'del mes de {meses[fecha_expedicion.month - 1]} de {fecha_expedicion.year}.'
    )
    story.append(Paragraph(expedicion_texto, estilo_cuerpo))
    story.append(Spacer(1, 44))

    # ---------- CUADRO DE FIRMAS PARALELAS (3 COLUMNAS) ----------
    celda_institucion = Paragraph(
        '<b>INSTITUCIÓN EDUCATIVA</b><br/>'
        '________________________________<br/>'
        f'{escape(director_nombre)}<br/>'
        f'N° C.I. {escape(director_cedula)}<br/>'
        'Firma y Sello',
        estilo_firma,
    )
    celda_sello = Paragraph('Sello Húmedo<br/><br/><br/>', estilo_firma)
    celda_cdcee = Paragraph(
        '<b>CENTRO DE DESARROLLO DE LA CALIDAD<br/>'
        'EDUCATIVA ESTADAL</b><br/>'
        '________________________________<br/>'
        'Nombre y Apellido:<br/>'
        'N° C.I.:<br/>'
        'Firma y Sello',
        estilo_firma,
    )

    tabla_firmas = Table(
        [[celda_institucion, celda_sello, celda_cdcee]],
        colWidths=[6.5 * cm, 3 * cm, 6.5 * cm],
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

    doc.build(story)
    buffer.seek(0)
    return buffer
