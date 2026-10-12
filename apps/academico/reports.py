"""
Report generation module for academico app.
Contains all export functions (Excel, PDF, CSV) for students, enrollments, and attendance.
"""
import csv
from django.http import HttpResponse
from django.db.models import ProtectedError
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from xml.sax.saxutils import escape
from .models import Alumnos, GruposAcademicos, Inscripciones, Asistencias
from apps.core.models import GradosAcademicos as CoreGradosAcademicos, Secciones


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
    """Separa tipo y número de documento (ej: 'V-REMOVED_SECRET78' -> 'V', 'REMOVED_SECRET78')."""
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

def _fila_alumno(alumno):
    """Genera una fila de datos para exportación de alumnos (Excel/CSV)."""
    direccion = alumno.id_direccion_residencia
    representante = _primera_relacion(alumno, 'representantes_vinculados')

    repre_nombre = _obtener_nombre_y_apellido(representante) if representante else 'N/D'
    repre_tipo_doc, repre_num_doc = _separar_documento(representante.numero_documento_identidad) if representante else ('', '')
    repre_telefono = representante.telefono if representante else 'N/D'

    grado_nombre = alumno.grado.nombre_grado if alumno.grado else 'N/D'
    seccion_nombre = alumno.seccion.nombre_seccion if alumno.seccion else 'N/D'
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
        alumno.estado_inscripcion or 'N/D',
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
        alumno.grado.nombre_grado if alumno.grado else 'N/D',
        alumno.seccion.nombre_seccion if alumno.seccion else 'N/D',
        alumno.estado_inscripcion or 'N/D',
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
    representante = _primera_relacion(alumno, 'representantes_vinculados')

    repre_nombre = _obtener_nombre_y_apellido(representante) if representante else 'N/D'
    repre_tipo_doc, repre_num_doc = _separar_documento(representante.numero_documento_identidad) if representante else ('', '')
    repre_telefono = representante.telefono if representante else 'N/D'

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
