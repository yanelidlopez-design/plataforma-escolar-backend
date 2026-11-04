"""Exportaciones individuales de la boleta cualitativa."""

from copy import copy
from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.cell_range import CellRange


PLANTILLA_BOLETA = Path(__file__).parent / 'assets' / 'boleta_cualitativa_plantilla.xlsx'
INDICADORES = ('PL', 'L', 'PM', 'EP', 'I')
NOMBRES_LAPSOS = {
    1: 'PRIMER LAPSO PEDAGÓGICO',
    2: 'SEGUNDO LAPSO PEDAGÓGICO',
    3: 'TERCER LAPSO PEDAGÓGICO',
}
FILAS_APRENDIZAJES_INICIO = 22
FILAS_APRENDIZAJES_FIN = 38
FILA_SUGERENCIAS = 39
FILAS_SECCION_CRITERIOS = (21, 25)


def _nombre_completo(persona):
    return ' '.join(filter(None, [
        getattr(persona, 'primer_nombre', None),
        getattr(persona, 'segundo_nombre', None),
        getattr(persona, 'primer_apellido', None),
        getattr(persona, 'segundo_apellido', None),
    ])).strip()


def _filas_aprendizajes(evaluaciones, aprendizajes_alcanzados):
    if isinstance(aprendizajes_alcanzados, str):
        aprendizajes_alcanzados = [{'texto': aprendizajes_alcanzados}]

    filas = []
    for item in aprendizajes_alcanzados or []:
        filas.append({
            'texto': item.get('texto') or '',
            'indicador': item.get('indicador') or '',
        })

    if not filas:
        filas = [
            {
                'texto': (
                    eval_.criterio.descripcion_criterio
                    if eval_.criterio else ''
                ),
                'indicador': eval_.indicador or '',
            }
            for eval_ in evaluaciones
        ]

    return filas or [{'texto': 'Sin aprendizajes registrados.', 'indicador': ''}]


def _texto_excel(valor):
    texto = str(valor or '')
    if texto.startswith(('=', '+', '-', '@')):
        return f"'{texto}"
    return texto


def _agregar_filas_aprendizaje(ws, cantidad):
    disponibles = FILAS_APRENDIZAJES_FIN - FILAS_APRENDIZAJES_INICIO + 1
    adicionales = max(0, cantidad - disponibles)
    if not adicionales:
        return

    merges_originales = [
        CellRange(str(rango))
        for rango in ws.merged_cells.ranges
        if rango.min_row >= FILA_SUGERENCIAS
    ]
    for rango in merges_originales:
        ws.unmerge_cells(str(rango))

    alturas = {
        fila: ws.row_dimensions[fila].height
        for fila in list(ws.row_dimensions)
        if fila >= FILA_SUGERENCIAS
    }
    for fila in alturas:
        del ws.row_dimensions[fila]

    estilos_fila = [copy(ws.cell(FILAS_APRENDIZAJES_FIN, columna)._style) for columna in range(1, 14)]
    ws.insert_rows(FILA_SUGERENCIAS, adicionales)
    for desplazamiento in range(adicionales):
        fila = FILA_SUGERENCIAS + desplazamiento
        for columna, estilo in enumerate(estilos_fila, start=1):
            ws.cell(fila, columna)._style = copy(estilo)
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=6)

    for fila, altura in alturas.items():
        if altura is not None:
            ws.row_dimensions[fila + adicionales].height = altura

    for rango in merges_originales:
        rango.shift(row_shift=adicionales)
        ws.merge_cells(str(rango))

    ultima_fila = max(63 + adicionales, ws.max_row)
    ws.print_area = f'A1:M{ultima_fila}'


def _eliminar_seccion_criterios(ws):
    inicio, fin = FILAS_SECCION_CRITERIOS
    merges_originales = [CellRange(str(rango)) for rango in ws.merged_cells.ranges]
    for rango in merges_originales:
        ws.unmerge_cells(str(rango))

    alturas = {
        fila: ws.row_dimensions[fila].height
        for fila in list(ws.row_dimensions)
        if fila > fin
    }
    for fila in list(ws.row_dimensions):
        if fila >= inicio:
            del ws.row_dimensions[fila]

    ws.delete_rows(inicio, fin - inicio + 1)

    for fila, altura in alturas.items():
        if altura is not None:
            ws.row_dimensions[fila - (fin - inicio + 1)].height = altura

    for rango in merges_originales:
        if rango.min_row <= fin and rango.max_row >= inicio:
            continue
        if rango.min_row > fin:
            rango.shift(row_shift=-(fin - inicio + 1))
        ws.merge_cells(str(rango))


def generar_excel_boleta_cualitativa(
    alumno,
    periodo,
    evaluaciones,
    datos_grupo=None,
    aprendizajes_alcanzados=None,
):
    """Genera una boleta Excel individual conservando la plantilla institucional."""
    evaluaciones = list(evaluaciones)
    filas_aprendizaje = _filas_aprendizajes(evaluaciones, aprendizajes_alcanzados)

    wb = load_workbook(PLANTILLA_BOLETA)
    ws = wb.active
    ws.title = 'Boleta'
    _eliminar_seccion_criterios(ws)
    _agregar_filas_aprendizaje(ws, len(filas_aprendizaje))

    datos_grupo = datos_grupo or {}
    lapso = NOMBRES_LAPSOS.get(
        periodo.numero_periodo,
        f'LAPSO {periodo.numero_periodo}',
    )
    año_actual = date.today().year
    año_escolar = datos_grupo.get('periodo_escolar') or f'{año_actual}-{año_actual + 1}'
    fecha_nacimiento = alumno.fecha_nacimiento
    edad = ''
    if fecha_nacimiento:
        hoy = date.today()
        edad = hoy.year - fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day)
        )

    representante_nombre = datos_grupo.get('representante', '')
    docente = datos_grupo.get('docente', '')
    valores = {
        'A12': f'INFORME DESCRIPTIVO DE EDUCACIÓN PRIMARIA\n{lapso}\nAÑO ESCOLAR: {año_escolar}',
        'A16': f'ESTUDIANTE: {_nombre_completo(alumno)}',
        'F16': f'C.E./C.I: {alumno.cedula_escolar or alumno.numero_documento_identidad or ""}',
        'A17': f'Grado: {datos_grupo.get("grado", "")}',
        'C17': f'Sección: {datos_grupo.get("seccion", "")}',
        'E17': f'Edad: {edad}',
        'F17': (
            'Fecha de Nacimiento: '
            f'{fecha_nacimiento.strftime("%d/%m/%Y") if fecha_nacimiento else ""}'
        ),
        'A18': f'Representante: {representante_nombre}',
        'A19': f'Docente del Grado: {docente}',
        'A20': f'P.A: {datos_grupo.get("proyecto_aprendizaje", "")}',
    }
    for celda, valor in valores.items():
        ws[celda] = _texto_excel(valor)

    for indice, aprendizaje in enumerate(filas_aprendizaje):
        fila = FILAS_APRENDIZAJES_INICIO + indice
        ws.cell(fila, 1, _texto_excel(aprendizaje['texto']))
        for columna, indicador in enumerate(INDICADORES, start=7):
            ws.cell(
                fila,
                columna,
                'X' if aprendizaje['indicador'] == indicador else '',
            )

    sugerencias = list(dict.fromkeys(
        [
            (item.get('sugerencias') or '').strip()
            for item in (aprendizajes_alcanzados or [])
            if isinstance(item, dict) and (item.get('sugerencias') or '').strip()
        ] + [
            evaluacion.sugerencias.strip()
            for evaluacion in evaluaciones
            if evaluacion.sugerencias and evaluacion.sugerencias.strip()
        ]
    ))
    ws['A40'] = _texto_excel(sugerencias[0] if sugerencias else '')
    ws['A41'] = _texto_excel('\n'.join(sugerencias[1:]))
    ws['B53'] = date.today().strftime('%d/%m/%Y')
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.print_area = f'A1:M{max(58 + max(0, len(filas_aprendizaje) - 17), ws.max_row)}'

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generar_pdf_boleta_cualitativa(
    alumno,
    periodo,
    evaluaciones,
    datos_grupo=None,
    aprendizajes_alcanzados=None,
):
    """Genera el PDF individual con las secciones y la escala de la plantilla."""
    import io
    from zipfile import ZipFile

    from django.utils import timezone
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    evaluaciones = list(evaluaciones)
    filas_aprendizaje = _filas_aprendizajes(evaluaciones, aprendizajes_alcanzados)
    datos_grupo = datos_grupo or {}
    año_actual = date.today().year
    año_escolar = datos_grupo.get('periodo_escolar') or f'{año_actual}-{año_actual + 1}'
    lapso = NOMBRES_LAPSOS.get(
        periodo.numero_periodo,
        f'LAPSO {periodo.numero_periodo}',
    )
    hoy = timezone.localdate()
    edad = ''
    if alumno.fecha_nacimiento:
        edad = hoy.year - alumno.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (alumno.fecha_nacimiento.month, alumno.fecha_nacimiento.day)
        )

    representante_nombre = datos_grupo.get('representante', '')
    nombre_alumno = _nombre_completo(alumno)
    docente = datos_grupo.get('docente', '')
    base = getSampleStyleSheet()
    membrete = ParagraphStyle(
        'BoletaMembrete', parent=base['Normal'], fontName='Helvetica',
        fontSize=8, leading=10, alignment=TA_CENTER,
    )
    titulo = ParagraphStyle(
        'BoletaTitulo', parent=base['Normal'], fontName='Helvetica-Bold',
        fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=2,
    )
    etiqueta = ParagraphStyle(
        'BoletaEtiqueta', parent=base['Normal'], fontName='Helvetica-Bold',
        fontSize=7.5, leading=9, alignment=TA_LEFT,
    )
    texto = ParagraphStyle(
        'BoletaTexto', parent=base['Normal'], fontName='Helvetica',
        fontSize=7.5, leading=9, alignment=TA_LEFT,
    )
    centrado = ParagraphStyle(
        'BoletaCentrado', parent=texto, alignment=TA_CENTER,
    )

    def p(valor, estilo=texto):
        return Paragraph(escape(str(valor or '')).replace('\n', '<br/>'), estilo)

    margen = 1.1 * cm
    ancho = letter[0] - 2 * margen
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=margen,
        rightMargin=margen,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm,
        title=f'Boleta cualitativa - {nombre_alumno}',
        author='E.B. Creación San José',
    )

    membrete_texto = (
        'República Bolivariana De Venezuela\n'
        'Ministerio Del Poder Popular Para La Educación\n'
        'E.B Creación San José\n'
        'Dirección: Urb. San José Obrero, Sector I Calle 1 Manzana A-12\n'
        'Correo: Uensanjose4@Gmail.Com\n'
        'Cod. Dea OD12431208\nCalabozo-El Calvario'
    )
    logo = None
    with ZipFile(PLANTILLA_BOLETA) as plantilla:
        archivo_logo = next(
            (nombre for nombre in plantilla.namelist() if nombre.startswith('xl/media/image') and nombre.endswith('.png')),
            None,
        )
        if archivo_logo:
            logo = Image(
                io.BytesIO(plantilla.read(archivo_logo)),
                width=2.1 * cm,
                height=2.1 * cm,
                kind='proportional',
            )

    cabecera = Table(
        [[logo or '', p(membrete_texto, membrete)]],
        colWidths=[2.5 * cm, ancho - 2.5 * cm],
    )
    cabecera.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    historia = [
        cabecera,
        Spacer(1, 4),
        p(
            'INFORME DESCRIPTIVO DE EDUCACIÓN PRIMARIA\n'
            f'{lapso}\nAÑO ESCOLAR: {año_escolar}',
            titulo,
        ),
        Spacer(1, 5),
    ]

    fecha_nacimiento = (
        alumno.fecha_nacimiento.strftime('%d/%m/%Y')
        if alumno.fecha_nacimiento else ''
    )
    estudiante = [
        [p('ESTUDIANTE:', etiqueta), p(nombre_alumno), p('C.E./C.I:', etiqueta),
         p(alumno.cedula_escolar or alumno.numero_documento_identidad)],
        [p(f'Grado: {datos_grupo.get("grado", "")}', etiqueta),
         p(f'Sección: {datos_grupo.get("seccion", "")}', etiqueta),
         p(f'Edad: {edad}', etiqueta),
         p(f'Fecha de Nacimiento: {fecha_nacimiento}', etiqueta)],
        [p('Representante:', etiqueta), p(representante_nombre), '', ''],
        [p('Docente del Grado:', etiqueta), p(docente), '', ''],
        [p('P.A:', etiqueta), p(datos_grupo.get('proyecto_aprendizaje', '')), '', ''],
    ]
    tabla_estudiante = Table(
        estudiante,
        colWidths=[2.5 * cm, 6.5 * cm, 2.5 * cm, ancho - 11.5 * cm],
    )
    tabla_estudiante.setStyle(TableStyle([
        ('SPAN', (1, 2), (3, 2)),
        ('SPAN', (1, 3), (3, 3)),
        ('SPAN', (1, 4), (3, 4)),
        ('GRID', (0, 0), (-1, -1), 0.45, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    historia.extend([tabla_estudiante, Spacer(1, 5)])

    encabezado_aprendizaje = [
        p('Aprendizajes Alcanzados:', etiqueta),
        *[p(indicador, etiqueta) for indicador in INDICADORES],
    ]
    tabla_aprendizajes_data = [encabezado_aprendizaje]
    for aprendizaje in filas_aprendizaje:
        tabla_aprendizajes_data.append([
            p(aprendizaje['texto']),
            *[
                p('X', centrado) if aprendizaje['indicador'] == indicador else ''
                for indicador in INDICADORES
            ],
        ])
    tabla_aprendizajes = Table(
        tabla_aprendizajes_data,
        colWidths=[ancho - 5 * 1.25 * cm] + [1.25 * cm] * 5,
        repeatRows=1,
    )
    tabla_aprendizajes.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.45, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E7E6E6')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    historia.extend([tabla_aprendizajes, Spacer(1, 5)])

    sugerencias = list(dict.fromkeys(
        [
            (item.get('sugerencias') or '').strip()
            for item in (aprendizajes_alcanzados or [])
            if isinstance(item, dict) and (item.get('sugerencias') or '').strip()
        ] + [
            evaluacion.sugerencias.strip()
            for evaluacion in evaluaciones
            if evaluacion.sugerencias and evaluacion.sugerencias.strip()
        ]
    ))
    tabla_sugerencias = Table(
        [[p('Sugerencias:', etiqueta)], [p('\n'.join(sugerencias) or ' ')]],
        colWidths=[ancho],
    )
    tabla_sugerencias.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.45, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    leyenda = (
        'Criterios: PL: Plenamente Logrado   L: Logrado   '
        'PM: Por Mejorar   EP: En Proceso   I: Iniciado'
    )
    historia.extend([
        tabla_sugerencias,
        Spacer(1, 5),
        p(leyenda, texto),
        Spacer(1, 15),
    ])

    tabla_firmas = Table(
        [
            [p('Docente del Grado:', etiqueta), '', p('Directora', etiqueta)],
            ['', '', ''],
            [p('sello', texto), '', ''],
            [p(f'Fecha de entrega: {hoy.strftime("%d/%m/%Y")}', etiqueta), '', ''],
        ],
        colWidths=[ancho * 0.4, ancho * 0.2, ancho * 0.4],
        rowHeights=[18, 30, 30, 18],
    )
    tabla_firmas.setStyle(TableStyle([
        ('LINEABOVE', (0, 1), (0, 1), 0.6, colors.black),
        ('LINEABOVE', (2, 1), (2, 1), 0.6, colors.black),
        ('ALIGN', (2, 0), (2, 2), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    historia.append(tabla_firmas)

    doc.build(historia)
    buffer.seek(0)
    return buffer
