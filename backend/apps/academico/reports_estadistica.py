"""
Reportes de estadística mensual por grado y sección.
Genera la planilla estadística mensual (Resumen Estadístico)
similar a la planilla oficial de asistencia mensual.
"""
from datetime import date, timedelta
from calendar import monthrange
from collections import defaultdict
from html import escape

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.academico.models import (
    GruposAcademicos,
    Inscripciones,
    Asistencias,
)

ESTADISTICA_MENSUAL_ENCABEZADOS = [
    'Apellidos y Nombres',
    'Ingreso',
    'Egreso',
    'Fecha y Lugar de Nacimiento',
    'Edad',
    'Sexo',
    'Procedencia',
]


def _calcular_edad(fecha_nacimiento, fecha_referencia):
    """Calcula la edad en años cumplidos."""
    if not fecha_nacimiento or not fecha_referencia:
        return 0
    edad = fecha_referencia.year - fecha_nacimiento.year
    if (fecha_referencia.month, fecha_referencia.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        edad -= 1
    return edad


def _genero_abreviado(genero):
    """Devuelve 'V' para varón/masculino, 'H' para hembra/femenino."""
    if not genero:
        return ''
    g = genero.strip().lower()
    if g in ['masculino', 'm', 'varón', 'v']:
        return 'V'
    if g in ['femenino', 'f', 'hembra', 'h']:
        return 'H'
    return genero[:1].upper()


def _contar_por_genero(queryset):
    """Cuenta varones, hembras y total de un queryset de Inscripciones."""
    varones = queryset.filter(alumno__genero__iexact='Masculino').count()
    hembras = queryset.filter(alumno__genero__iexact='Femenino').count()
    return varones, hembras, varones + hembras


def generar_estadistica_mensual_excel(grupo_id, año, mes):
    """
    Genera la planilla estadística mensual por grado y sección en formato Excel.

    Incluye:
    - Membrete institucional
    - Matrícula (ingresos, egresos, alumnos al último día)
    - Clasificación de edades y sexo
    - Total asistencia
    - Listado de alumnos con datos individuales

    Args:
        grupo_id: ID del grupo académico
        año: Año del reporte
        mes: Mes del reporte (1-12)

    Returns:
        HttpResponse con el archivo Excel
    """
    grupo = GruposAcademicos.objects.select_related('grado', 'seccion', 'periodo').get(id_grupo=grupo_id)
    grado_nombre = grupo.grado.nombre_grado
    seccion_nombre = grupo.seccion.nombre_seccion
    periodo_nombre = grupo.periodo.nombre_periodo

    # Rango de fechas del mes
    primer_dia = date(año, mes, 1)
    ultimo_dia_num = monthrange(año, mes)[1]
    ultimo_dia = date(año, mes, ultimo_dia_num)
    nombre_mes = primer_dia.strftime('%B').capitalize()

    # Obtener inscripciones del grupo para este período
    inscripciones = Inscripciones.objects.select_related('alumno', 'grupo').filter(
        grupo_id=grupo_id
    )

    # Alumnos actualmente activos en este grupo
    alumnos_activos = inscripciones.filter(estado_inscripcion='Activa')

    # Ingresos del mes (inscritos en este mes)
    ingresos_mes = alumnos_activos.filter(
        fecha_inscripcion__year=año,
        fecha_inscripcion__month=mes
    )

    # Egresos del mes (retirados/graduados en este mes)
    egresos_mes = inscripciones.filter(
        estado_inscripcion__in=['Retirado', 'Graduado'],
        fecha_inscripcion__year=año,
        fecha_inscripcion__month=mes
    )

    # Contadores por género
    v_ing, h_ing, t_ing = _contar_por_genero(ingresos_mes)
    v_egr, h_egr, t_egr = _contar_por_genero(egresos_mes)
    v_act, h_act, t_act = _contar_por_genero(alumnos_activos)

    # Clasificación por edad y sexo
    edades_stats = defaultdict(lambda: {'V': 0, 'H': 0, 'rep': 0})
    for ins in alumnos_activos:
        alumno = ins.alumno
        edad = _calcular_edad(alumno.fecha_nacimiento, ultimo_dia)
        gen = _genero_abreviado(alumno.genero)
        if gen == 'V':
            edades_stats[edad]['V'] += 1
        elif gen == 'H':
            edades_stats[edad]['H'] += 1
        edades_stats[edad]['rep'] = 0

    # Asistencia del mes - contar presentes por género
    asistencias_mes = Asistencias.objects.filter(
        grupo_id=grupo_id,
        fecha__year=año,
        fecha__month=mes
    )
    v_pres = 0
    h_pres = 0
    for asis in asistencias_mes.filter(estado='P'):
        gen = _genero_abreviado(asis.alumno.genero)
        if gen == 'V':
            v_pres += 1
        elif gen == 'H':
            h_pres += 1

        # CREAR EL ARCHIVO EXCEL
        wb = Workbook()
    ws = wb.active
    ws.title = f"Estadística {nombre_mes} {año}"

    # Estilos
    fuente_titulo = Font(name="Arial", size=14, bold=True, color="1F4E78")
    fuente_subtitulo = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    fuente_encabezado = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    fuente_celda = Font(name="Arial", size=10, color="000000")
    fuente_negrita = Font(name="Arial", size=10, bold=True, color="000000")

    relleno_azul = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    relleno_gris = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

    borde_fino = Side(style="thin", color="000000")
    borde_completo = Border(left=borde_fino, right=borde_fino, top=borde_fino, bottom=borde_fino)

    alinear_centro = Alignment(horizontal="center", vertical="center", wrap_text=True)
    alinear_izquierda = Alignment(horizontal="left", vertical="center", wrap_text=True)

    fila_actual = 1

    # ---------- MEMBRETE INSTITUCIONAL ----------
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=7)
    celda = ws.cell(row=fila_actual, column=1, value="REPÚBLICA BOLIVARIANA DE VENEZUELA")
    celda.font = fuente_titulo
    celda.alignment = alinear_centro
    fila_actual += 1

    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=7)
    celda = ws.cell(row=fila_actual, column=1, value="Ministerio del Poder Popular para la Educación")
    celda.font = Font(name="Arial", size=11, color="1F4E78")
    celda.alignment = alinear_centro
    fila_actual += 1

    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=7)
    celda = ws.cell(row=fila_actual, column=1, value="E.B Creación San José")
    celda.font = Font(name="Arial", size=11, color="1F4E78")
    celda.alignment = alinear_centro
    fila_actual += 1

    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=7)
    celda = ws.cell(row=fila_actual, column=1, value="Cod. DEA: OD12431208 | Calabozo - El Calvario")
    celda.font = Font(name="Arial", size=9, color="666666")
    celda.alignment = alinear_centro
    fila_actual += 2

    # ---------- TÍTULO DEL REPORTE ----------
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=7)
    celda = ws.cell(row=fila_actual, column=1, value="RESUMEN ESTADÍSTICO MENSUAL")
    celda.font = fuente_titulo
    celda.alignment = alinear_centro
    fila_actual += 1

    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=7)
    celda = ws.cell(row=fila_actual, column=1,
                    value=f"Año Escolar: {periodo_nombre}    Mes: {nombre_mes} {año}    Grado: {grado_nombre}    Sección: {seccion_nombre}")
    celda.font = Font(name="Arial", size=10, bold=True, color="000000")
    celda.alignment = alinear_centro
    fila_actual += 2

    # ---------- SECCIÓN: MATRÍCULA ----------
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=7)
    celda = ws.cell(row=fila_actual, column=1, value="MATRÍCULA")
    celda.font = fuente_subtitulo
    celda.fill = relleno_azul
    celda.alignment = alinear_centro
    fila_actual += 1

    # Encabezados de días
    dias_semana = ['L', 'M', 'Mi', 'J', 'V', 'S']
    ws.cell(row=fila_actual, column=1, value="DÍA")
    ws.cell(row=fila_actual, column=2, value="FECHA")
    for i, d in enumerate(dias_semana):
        ws.cell(row=fila_actual, column=3+i, value=d)
    ws.cell(row=fila_actual, column=9, value="TOTAL")
    for col in range(1, 10):
        c = ws.cell(row=fila_actual, column=col)
        c.font = fuente_encabezado
        c.fill = relleno_azul
        c.alignment = alinear_centro
        c.border = borde_completo
    fila_actual += 1

    # Filas de días (vacías para llenar manualmente)
    for dia_num in range(1, ultimo_dia_num + 1):
        fecha_dia = date(año, mes, dia_num)
        nombre_dia = dias_semana[fecha_dia.weekday() % len(dias_semana)]
        ws.cell(row=fila_actual, column=1, value=nombre_dia)
        ws.cell(row=fila_actual, column=2, value=fecha_dia.strftime('%d/%m'))
        for col in range(3, 10):
            ws.cell(row=fila_actual, column=col, value="")
        for col in range(1, 10):
            c = ws.cell(row=fila_actual, column=col)
            c.border = borde_completo
            c.font = fuente_celda
        fila_actual += 1

    # Filas resumen de matrícula
    filas_resumen = [
        ("ALUMNOS AL 1ER DÍA DEL MES", v_act, h_act, t_act),
        ("INGRESOS DEL MES", v_ing, h_ing, t_ing),
        ("EGRESOS DEL MES", v_egr, h_egr, t_egr),
        ("ALUMNOS AL ÚLTIMO DÍA DEL MES", v_act, h_act, t_act),
    ]
    for etiqueta, v, h, t in filas_resumen:
        ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=2)
        ws.cell(row=fila_actual, column=1, value=etiqueta)
        ws.cell(row=fila_actual, column=3, value=v)
        ws.cell(row=fila_actual, column=4, value=h)
        ws.cell(row=fila_actual, column=5, value=t)
        for col in range(1, 6):
            c = ws.cell(row=fila_actual, column=col)
            c.border = borde_completo
            c.font = fuente_negrita
            c.fill = relleno_gris
        fila_actual += 1
    fila_actual += 1

    # ---------- SECCIÓN: CLASIFICACIÓN DE EDADES Y SEXO ----------
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=7)
    celda = ws.cell(row=fila_actual, column=1, value="CLASIFICACIÓN DE EDADES Y SEXO")
    celda.font = fuente_subtitulo
    celda.fill = relleno_azul
    celda.alignment = alinear_centro
    fila_actual += 1

    # Encabezados
    ws.cell(row=fila_actual, column=1, value="EDAD")
    ws.cell(row=fila_actual, column=2, value="V")
    ws.cell(row=fila_actual, column=3, value="H")
    ws.cell(row=fila_actual, column=5, value="REPETENTES")
    ws.cell(row=fila_actual, column=6, value="V")
    ws.cell(row=fila_actual, column=7, value="H")
    for col in [1, 2, 3, 5, 6, 7]:
        c = ws.cell(row=fila_actual, column=col)
        c.font = fuente_encabezado
        c.fill = relleno_azul
        c.alignment = alinear_centro
        c.border = borde_completo
    fila_actual += 1

    # Filas por edad
    for edad in sorted(edades_stats.keys()):
        stats = edades_stats[edad]
        ws.cell(row=fila_actual, column=1, value=edad)
        ws.cell(row=fila_actual, column=2, value=stats['V'])
        ws.cell(row=fila_actual, column=3, value=stats['H'])
        ws.cell(row=fila_actual, column=5, value=stats['rep'])
        ws.cell(row=fila_actual, column=6, value=stats['V'])
        ws.cell(row=fila_actual, column=7, value=stats['H'])
        for col in [1, 2, 3, 5, 6, 7]:
            c = ws.cell(row=fila_actual, column=col)
            c.border = borde_completo
            c.font = fuente_celda
        fila_actual += 1
    fila_actual += 1

    # ---------- SECCIÓN: TOTAL ASISTENCIA ----------
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=7)
    celda = ws.cell(row=fila_actual, column=1, value="TOTAL ASISTENCIA")
    celda.font = fuente_subtitulo
    celda.fill = relleno_azul
    celda.alignment = alinear_centro
    fila_actual += 1

    ws.cell(row=fila_actual, column=2, value="V")
    ws.cell(row=fila_actual, column=3, value="H")
    ws.cell(row=fila_actual, column=5, value="TOTAL")
    for col in [2, 3, 5]:
        c = ws.cell(row=fila_actual, column=col)
        c.font = fuente_encabezado
        c.fill = relleno_azul
        c.alignment = alinear_centro
        c.border = borde_completo
    fila_actual += 1

    ws.cell(row=fila_actual, column=2, value=v_pres)
    ws.cell(row=fila_actual, column=3, value=h_pres)
    ws.cell(row=fila_actual, column=5, value=v_pres + h_pres)
    for col in [2, 3, 5]:
        c = ws.cell(row=fila_actual, column=col)
        c.border = borde_completo
        c.font = fuente_negrita
        c.fill = relleno_gris
    fila_actual += 2

    # ---------- SECCIÓN: LISTADO DE ALUMNOS ----------
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=7)
    celda = ws.cell(row=fila_actual, column=1, value="LISTADO DE ALUMNOS - INGRESOS Y EGRESOS")
    celda.font = fuente_subtitulo
    celda.fill = relleno_azul
    celda.alignment = alinear_centro
    fila_actual += 1

    # Encabezados
    for col_num, encabezado in enumerate(ESTADISTICA_MENSUAL_ENCABEZADOS, 1):
        c = ws.cell(row=fila_actual, column=col_num, value=encabezado)
        c.font = fuente_encabezado
        c.fill = relleno_azul
        c.alignment = alinear_centro
        c.border = borde_completo
    fila_actual += 1

    # Filas de alumnos
    for ins in alumnos_activos.order_by('alumno__primer_apellido', 'alumno__primer_nombre'):
        alumno = ins.alumno
        nombre_completo = f"{alumno.primer_apellido} {alumno.segundo_apellido or ''} {alumno.primer_nombre} {alumno.segundo_nombre or ''}".strip()
        fecha_ingreso = ins.fecha_inscripcion.strftime('%d/%m/%Y') if ins.fecha_inscripcion else ''
        fecha_egreso = ''
        fecha_nac = alumno.fecha_nacimiento.strftime('%d/%m/%Y') if alumno.fecha_nacimiento else ''
        lugar_nac = alumno.lugar_nacimiento or ''
        edad = _calcular_edad(alumno.fecha_nacimiento, ultimo_dia)
        sexo = _genero_abreviado(alumno.genero)
        try:
            direccion = alumno.id_direccion_residencia
            procedencia = f"{direccion.ciudad}, {direccion.estado}" if direccion else (alumno.lugar_nacimiento or '')
        except Exception:
            procedencia = alumno.lugar_nacimiento or ''

        valores = [
            nombre_completo,
            fecha_ingreso,
            fecha_egreso,
            f"{fecha_nac} / {lugar_nac}",
            edad,
            sexo,
            procedencia,
        ]
        for col_num, valor in enumerate(valores, 1):
            c = ws.cell(row=fila_actual, column=col_num, value=valor)
            c.font = fuente_celda
            c.alignment = alinear_izquierda
            c.border = borde_completo
        fila_actual += 1

    # Ajustar ancho de columnas
    anchos = [25, 12, 12, 30, 8, 8, 20]
    for i, ancho in enumerate(anchos, 1):
        ws.column_dimensions[chr(64 + i)].width = ancho

    # Generar respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="estadistica_mensual_{grado_nombre}_{seccion_nombre}_{año}_{mes:02d}.xlsx"'
    wb.save(response)
    return response


def _rango_corte_mensual(año, mes):
    fecha_corte = date(año, mes, 25)
    fecha_inicio = (date(año, mes, 1) - timedelta(days=1)).replace(day=26)
    return fecha_inicio, fecha_corte


def _fechas_habiles_periodo_mensual(año, mes):
    fecha_inicio, fecha_corte = _rango_corte_mensual(año, mes)
    return [
        fecha_inicio + timedelta(days=desplazamiento)
        for desplazamiento in range((fecha_corte - fecha_inicio).days + 1)
        if (fecha_inicio + timedelta(days=desplazamiento)).weekday() < 6
    ]


def _fecha_inscripcion(inscripcion):
    fecha = inscripcion.fecha_inscripcion
    return fecha.date() if hasattr(fecha, 'date') else fecha


def _conteo_genero(inscripciones):
    varones = sum(_genero_abreviado(item.alumno.genero) == 'V' for item in inscripciones)
    hembras = sum(_genero_abreviado(item.alumno.genero) == 'H' for item in inscripciones)
    return varones, hembras, len(inscripciones)


def _obtener_docente_asignado(grupo, inscripciones):
    if grupo.profesor_director:
        return grupo.profesor_director

    docentes_alumnos = {}
    for inscripcion in inscripciones:
        docente = getattr(inscripcion.alumno, 'id_profesor_encargado', None)
        if docente:
            docente_id = getattr(docente, 'pk', None) or getattr(docente, 'id_profesor', None)
            docentes_alumnos[docente_id or id(docente)] = docente
    return next(iter(docentes_alumnos.values())) if len(docentes_alumnos) == 1 else None


def generar_estadistica_mensual_pdf(grupo_id, año, mes):
    """Genera la estadística de asistencia del 26 al 25 de cada ciclo."""
    from apps.academico.models import GruposAcademicos, Inscripciones, Asistencias

    grupo = GruposAcademicos.objects.select_related(
        'grado', 'seccion', 'periodo', 'profesor_director'
    ).get(pk=grupo_id)
    fecha_inicio, fecha_corte = _rango_corte_mensual(año, mes)
    dias_habiles = _fechas_habiles_periodo_mensual(año, mes)
    nombre_mes_inicio = (
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
    )[fecha_inicio.month - 1]
    nombre_mes_fin = (
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
    )[mes - 1]

    inscripciones = list(
        Inscripciones.objects.filter(grupo_id=grupo_id)
        .select_related(
            'alumno',
            'alumno__id_direccion_residencia',
            'alumno__id_profesor_encargado',
        )
        .order_by('alumno__primer_apellido', 'alumno__primer_nombre')
    )
    def matriculado_en(inscripcion, fecha_referencia):
        fecha_ingreso = _fecha_inscripcion(inscripcion)
        if fecha_ingreso and fecha_ingreso > fecha_referencia:
            return False
        alumno = inscripcion.alumno
        fecha_egreso = getattr(alumno, 'fecha_egreso', None)
        if fecha_egreso:
            return fecha_egreso > fecha_referencia
        if getattr(alumno, 'estatus_general', '') in ('Egresado', 'Retirado'):
            return False
        return inscripcion.estado_inscripcion == 'Activa'

    vigentes = [inscripcion for inscripcion in inscripciones if matriculado_en(inscripcion, fecha_corte)]
    matricula_inicio = [inscripcion for inscripcion in inscripciones if matriculado_en(inscripcion, fecha_inicio)]
    ingresos_mes = [
        inscripcion for inscripcion in inscripciones
        if _fecha_inscripcion(inscripcion) is not None
        and fecha_inicio <= _fecha_inscripcion(inscripcion) <= fecha_corte
    ]
    egresos_mes = [
        inscripcion for inscripcion in inscripciones
        if getattr(inscripcion.alumno, 'estatus_general', '') in ('Egresado', 'Retirado')
        and getattr(inscripcion.alumno, 'fecha_egreso', None) is not None
        and fecha_inicio <= inscripcion.alumno.fecha_egreso <= fecha_corte
    ]
    egresos_sin_fecha = sum(
        getattr(inscripcion.alumno, 'estatus_general', '') in ('Egresado', 'Retirado')
        and getattr(inscripcion.alumno, 'fecha_egreso', None) is None
        for inscripcion in inscripciones
    )
    alumnos_del_periodo = [
        inscripcion for inscripcion in inscripciones
        if (_fecha_inscripcion(inscripcion) is None or _fecha_inscripcion(inscripcion) <= fecha_corte)
        and (matriculado_en(inscripcion, fecha_corte) or inscripcion in egresos_mes)
    ]
    v_inicio, h_inicio, t_inicio = _conteo_genero(matricula_inicio)
    v_ingreso, h_ingreso, t_ingreso = _conteo_genero(ingresos_mes)
    v_egreso, h_egreso, t_egreso = _conteo_genero(egresos_mes)
    v_corte, h_corte, t_corte = _conteo_genero(vigentes)

    asistencias = Asistencias.objects.filter(
        grupo_id=grupo_id,
        fecha__in=dias_habiles,
    ).select_related('alumno')
    presentes_por_fecha = defaultdict(lambda: {'V': 0, 'H': 0})
    total_presentes = {'V': 0, 'H': 0}
    for asistencia in asistencias.filter(estado='P'):
        genero = _genero_abreviado(asistencia.alumno.genero)
        if genero in total_presentes:
            presentes_por_fecha[asistencia.fecha][genero] += 1
            total_presentes[genero] += 1

    edades = defaultdict(lambda: {'V': 0, 'H': 0, 'repV': 0, 'repH': 0})
    for inscripcion in vigentes:
        edad = _calcular_edad(inscripcion.alumno.fecha_nacimiento, fecha_corte)
        genero = _genero_abreviado(inscripcion.alumno.genero)
        if genero in ('V', 'H'):
            edades[edad][genero] += 1
            if getattr(inscripcion.alumno, 'repitiente', False):
                edades[edad][f'rep{genero}'] += 1

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="estadistica_mensual_{grupo_id}_{año}_{mes:02d}.pdf"'
    )
    doc = SimpleDocTemplate(
        response, pagesize=letter, rightMargin=24, leftMargin=24,
        topMargin=22, bottomMargin=22,
    )
    base = getSampleStyleSheet()
    titulo = ParagraphStyle(
        'EstadisticaTitulo', parent=base['Normal'], fontName='Helvetica-Bold',
        fontSize=9, leading=11, alignment=1,
    )
    subtitulo = ParagraphStyle(
        'EstadisticaSubtitulo', parent=base['Normal'], fontName='Helvetica',
        fontSize=7, leading=9, alignment=1,
    )
    encabezado = ParagraphStyle(
        'EstadisticaEncabezado', parent=base['Normal'], fontName='Helvetica-Bold',
        fontSize=6.5, leading=7.5, alignment=1,
    )
    celda = ParagraphStyle(
        'EstadisticaCelda', parent=base['Normal'], fontName='Helvetica',
        fontSize=6.5, leading=7.5,
    )
    centrado = ParagraphStyle('EstadisticaCentrado', parent=celda, alignment=1)
    seccion = ParagraphStyle(
        'EstadisticaSeccion', parent=base['Normal'], fontName='Helvetica-Bold',
        fontSize=7, leading=8, alignment=1,
    )

    def texto(valor, estilo=celda):
        return Paragraph(escape(str(valor if valor is not None else '')), estilo)

    azul = colors.HexColor('#24476B')
    gris = colors.HexColor('#E8EDF2')

    def tabla_estilo(filas_encabezado=1):
        return TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#626B73')),
            ('BACKGROUND', (0, 0), (-1, filas_encabezado - 1), azul),
            ('TEXTCOLOR', (0, 0), (-1, filas_encabezado - 1), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('ROWBACKGROUNDS', (0, filas_encabezado), (-1, -1), [colors.white, gris]),
        ])

    historia = [
        texto('REPÚBLICA BOLIVARIANA DE VENEZUELA', titulo),
        texto('Ministerio del Poder Popular para la Educación', subtitulo),
        texto('E.B. Creación San José', subtitulo),
        texto('Urb. San José Obrero, Calabozo - El Calvario | Cod. DEA: OD12431208', subtitulo),
        Spacer(1, 5),
        texto('RESUMEN ESTADÍSTICO MENSUAL', titulo),
    ]
    docente = _obtener_docente_asignado(grupo, vigentes)
    nombre_docente = ' '.join(filter(None, [
        getattr(docente, 'primer_nombre', None),
        getattr(docente, 'segundo_nombre', None),
        getattr(docente, 'primer_apellido', None),
        getattr(docente, 'segundo_apellido', None),
    ])) if docente else 'No asignado'
    historia.extend([
        texto(
            f'Año escolar: {grupo.periodo.nombre_periodo} | '
            f'Corte: 26 de {nombre_mes_inicio} al 25 de {nombre_mes_fin} {año} | '
            f'Días hábiles: {len(dias_habiles)} | Docente: {nombre_docente} | '
            f'Grado: {grupo.grado.nombre_grado} | Sección: {grupo.seccion.nombre_seccion}',
            subtitulo,
        ),
        Spacer(1, 7),
    ])

    dias_data = [[texto('DÍA', encabezado), texto('FECHA', encabezado), texto('V', encabezado),
                  texto('H', encabezado), texto('TOTAL', encabezado)]]
    for dia in dias_habiles:
        conteo = presentes_por_fecha[dia]
        dias_data.append([
            texto(('L', 'M', 'M', 'J', 'V', 'S')[dia.weekday()], centrado),
            texto(dia.strftime('%d/%m'), centrado),
            texto(conteo['V'], centrado),
            texto(conteo['H'], centrado),
            texto(conteo['V'] + conteo['H'], centrado),
        ])
    dias_data.append([
        texto('TOTAL', encabezado), texto(''), texto(total_presentes['V'], centrado),
        texto(total_presentes['H'], centrado),
        texto(sum(total_presentes.values()), centrado),
    ])
    tabla_dias = Table(dias_data, colWidths=[24, 36, 27, 27, 38], repeatRows=1)
    tabla_dias.setStyle(tabla_estilo())
    tabla_dias.setStyle(TableStyle([('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold')]))

    tabla_matricula = Table([
        [texto('MATRÍCULA', seccion), texto('V', encabezado), texto('H', encabezado), texto('TOTAL', encabezado)],
        [texto('Alumnos al inicio del período (día 26)'), texto(v_inicio, centrado), texto(h_inicio, centrado), texto(t_inicio, centrado)],
        [texto('Ingresos del período'), texto(v_ingreso, centrado), texto(h_ingreso, centrado), texto(t_ingreso, centrado)],
        [texto('Egresos del período'), texto(v_egreso, centrado), texto(h_egreso, centrado), texto(t_egreso, centrado)],
        [texto('Alumnos al corte del día 25'), texto(v_corte, centrado), texto(h_corte, centrado), texto(t_corte, centrado)],
    ], colWidths=[205, 36, 36, 43])
    tabla_matricula.setStyle(tabla_estilo())
    tabla_matricula.setStyle(TableStyle([
        ('SPAN', (0, 0), (0, 0)),
        ('BACKGROUND', (0, 0), (0, 0), azul),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
        ('ALIGN', (1, 0), (-1, 0), 'CENTER'),
    ]))

    edades_data = [
        [texto('EDAD', encabezado), texto('SEXO', encabezado), '', '', texto('REPITIENTES', encabezado), '', ''],
        [texto(''), texto('V', encabezado), texto('H', encabezado), texto('T', encabezado),
         texto('V', encabezado), texto('H', encabezado), texto('T', encabezado)],
    ]
    for edad, conteo in sorted(edades.items()):
        edades_data.append([
            texto(edad, centrado), texto(conteo['V'], centrado), texto(conteo['H'], centrado),
            texto(conteo['V'] + conteo['H'], centrado), texto(conteo['repV'], centrado),
            texto(conteo['repH'], centrado), texto(conteo['repV'] + conteo['repH'], centrado),
        ])
    if not edades:
        edades_data.append([texto('—', centrado)] * 7)
    tabla_edades = Table(edades_data, colWidths=[42, 34, 34, 34, 42, 34, 34])
    tabla_edades.setStyle(tabla_estilo(filas_encabezado=2))
    tabla_edades.setStyle(TableStyle([
        ('SPAN', (1, 0), (3, 0)),
        ('SPAN', (4, 0), (6, 0)),
    ]))
    lado_derecho = Table([
        [tabla_matricula],
        [Spacer(1, 5)],
        [texto('CLASIFICACIÓN DE EDADES Y SEXO', seccion)],
        [tabla_edades],
    ], colWidths=[356])
    lado_derecho.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    resumen_superior = Table([[tabla_dias, lado_derecho]], colWidths=[160, 356])
    resumen_superior.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    historia.extend([
        resumen_superior,
        Spacer(1, 6),
        texto('TOTAL ASISTENCIA', seccion),
    ])
    tabla_total = Table([
        [texto('V', encabezado), texto('H', encabezado), texto('TOTAL', encabezado)],
        [texto(total_presentes['V'], centrado), texto(total_presentes['H'], centrado),
         texto(sum(total_presentes.values()), centrado)],
    ], colWidths=[55, 55, 65])
    tabla_total.setStyle(tabla_estilo())
    historia.extend([tabla_total, Spacer(1, 7)])

    roster_data = [[texto(titulo_columna, encabezado) for titulo_columna in ESTADISTICA_MENSUAL_ENCABEZADOS]]
    for inscripcion in alumnos_del_periodo:
        alumno = inscripcion.alumno
        fecha_nacimiento = alumno.fecha_nacimiento
        direccion = alumno.id_direccion_residencia
        procedencia = (
            ', '.join(filter(None, [getattr(direccion, 'ciudad', ''), getattr(direccion, 'estado', '')]))
            if direccion else (alumno.lugar_nacimiento or '')
        )
        nombre = ' '.join(filter(None, [
            alumno.primer_apellido, alumno.segundo_apellido,
            alumno.primer_nombre, alumno.segundo_nombre,
        ]))
        roster_data.append([
            texto(nombre),
            texto(_fecha_inscripcion(inscripcion).strftime('%d/%m/%Y') if _fecha_inscripcion(inscripcion) else '', centrado),
            texto(
                alumno.fecha_egreso.strftime('%d/%m/%Y')
                if getattr(alumno, 'fecha_egreso', None)
                else (
                    f"{alumno.estatus_general} (sin fecha)"
                    if getattr(alumno, 'estatus_general', '') in ('Egresado', 'Retirado')
                    else ''
                ),
                centrado,
            ),
            texto(f'{fecha_nacimiento.strftime("%d/%m/%Y")} / {alumno.lugar_nacimiento or ""}'),
            texto(_calcular_edad(fecha_nacimiento, fecha_corte), centrado),
            texto(_genero_abreviado(alumno.genero), centrado),
            texto(procedencia),
        ])
    if len(roster_data) == 1:
        roster_data.append([texto('Sin alumnos inscritos en este corte.', centrado)] + [''] * 6)
    tabla_roster = Table(
        roster_data,
        colWidths=[116, 52, 52, 105, 32, 34, 125],
        repeatRows=1,
    )
    tabla_roster.setStyle(tabla_estilo())
    tabla_roster.setStyle(TableStyle([
        ('SPAN', (0, 1), (-1, 1)) if len(roster_data) == 2 and not vigentes else
         ('VALIGN', (0, 1), (-1, -1), 'TOP'),
    ]))
    historia.extend([
        texto('LISTADO DE ALUMNOS - INGRESOS Y EGRESOS', seccion),
        tabla_roster,
        Spacer(1, 4),
        texto(
            f'Egresos sin fecha registrados: {egresos_sin_fecha}. No se asignan a un mes hasta registrar la fecha real.',
            subtitulo,
        ),
    ])
    doc.build(historia)
    return response