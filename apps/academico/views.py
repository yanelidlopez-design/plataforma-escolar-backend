from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import HttpResponse
from django.conf import settings
from django.utils import timezone
import csv
import hmac
import logging
import re
from xml.sax.saxutils import escape
import openpyxl
from openpyxl.styles import Font, PatternFill
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from datetime import date, datetime
from .models import Alumnos, GruposAcademicos, Inscripciones, Calificaciones, Asistencias
from .serializers import (
    AlumnosSerializer, GruposAcademicosSerializer,
    InscripcionesSerializer, CalificacionesSerializer, AsistenciasSerializer
)
from .permissions import EsProfesorOAdmin, EsAdministrador
from apps.core.models import ConfiguracionPlantel

logger = logging.getLogger(__name__)

@swagger_auto_schema(tags=['Alumnos'])
class AlumnosViewSet(viewsets.ModelViewSet):
    queryset = Alumnos.objects.select_related('id_direccion_residencia').prefetch_related('representantes_vinculados')
    serializer_class = AlumnosSerializer
    permission_classes = [EsProfesorOAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['cedula_escolar', 'numero_documento_identidad', 'primer_nombre', 'primer_apellido']
    ordering_fields = ['primer_apellido', 'primer_nombre']

    @swagger_auto_schema(
        operation_description='Obtener historial de inscripciones de un alumno',
        responses={200: InscripcionesSerializer(many=True)}
    )
    @action(detail=True, methods=['get'])
    def historial_inscripciones(self, request, pk=None):
        alumno = self.get_object()
        inscripciones = Inscripciones.objects.filter(alumno=alumno).select_related('periodo', 'grupo_academico')
        serializer = InscripcionesSerializer(inscripciones, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description='Obtener alumnos por sección',
        manual_parameters=[
            openapi.Parameter('grado', openapi.IN_QUERY, description='ID del grado', type=openapi.TYPE_INTEGER),
            openapi.Parameter('seccion', openapi.IN_QUERY, description='ID de la sección', type=openapi.TYPE_INTEGER),
            openapi.Parameter('periodo', openapi.IN_QUERY, description='ID del período (opcional)', type=openapi.TYPE_INTEGER, required=False),
        ],
        responses={200: AlumnosSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def por_seccion(self, request):
        """
        Obtener alumnos activos por grado y sección.
        Ejemplo: GET /api/academico/alumnos/por_seccion/?grado=1&seccion=1&periodo=1
        """
        grado_id = request.query_params.get('grado')
        seccion_id = request.query_params.get('seccion')
        periodo_id = request.query_params.get('periodo')

        if not grado_id or not seccion_id:
            return Response(
                {'error': 'Parámetros grado y seccion son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Filtrar grupos por grado, sección y opcionalmente por período
        grupos_query = GruposAcademicos.objects.filter(
            grado_id=grado_id,
            seccion_id=seccion_id
        )

        if periodo_id:
            grupos_query = grupos_query.filter(periodo_id=periodo_id)

        # Obtener inscripciones activas en esos grupos
        inscripciones = Inscripciones.objects.filter(
            grupo__in=grupos_query,
            estado_inscripcion='Activa'
        ).select_related('alumno')

        alumnos = [inscripcion.alumno for inscripcion in inscripciones]
        serializer = AlumnosSerializer(alumnos, many=True)
        return Response(serializer.data)


@swagger_auto_schema(tags=['Grupos Académicos'])
class GruposAcademicosViewSet(viewsets.ModelViewSet):
    queryset = GruposAcademicos.objects.select_related('periodo', 'grado', 'seccion', 'turno', 'profesor_director')
    serializer_class = GruposAcademicosSerializer
    permission_classes = [EsAdministrador]
    filterset_fields = ['periodo', 'grado', 'seccion', 'turno', 'profesor_director']

    @swagger_auto_schema(
        operation_description='Obtener alumnos activos en un grupo académico',
        responses={200: AlumnosSerializer(many=True)}
    )
    @action(detail=True, methods=['get'], url_path='alumnos-activos')
    def alumnos_activos(self, request, pk=None):
        grupo_academico = self.get_object()
        inscripciones = Inscripciones.objects.filter(
            grupo=grupo_academico,
            estado_inscripcion='Activa'
        ).select_related('alumno')
        alumnos = [registro.alumno for registro in inscripciones]
        serializer = AlumnosSerializer(alumnos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



@swagger_auto_schema(tags=['Inscripciones'])
class InscripcionesViewSet(viewsets.ModelViewSet):
    queryset = Inscripciones.objects.select_related('alumno', 'grupo', 'grupo__periodo')
    serializer_class = InscripcionesSerializer
    permission_classes = [EsProfesorOAdmin]
    filterset_fields = ['estado_inscripcion', 'alumno', 'grupo']
    search_fields = ['alumno__primer_nombre', 'alumno__primer_apellido', 'alumno__cedula_escolar']


@swagger_auto_schema(tags=['Calificaciones'])
class CalificacionesViewSet(viewsets.ModelViewSet):
    queryset = Calificaciones.objects.select_related('inscripcion__alumno', 'id_profesor')
    serializer_class = CalificacionesSerializer
    permission_classes = [EsProfesorOAdmin]
    filterset_fields = ['inscripcion', 'id_profesor', 'calificacion']
    search_fields = ['inscripcion__alumno__primer_nombre', 'inscripcion__alumno__primer_apellido']

    @swagger_auto_schema(
        operation_description='Obtener calificaciones por alumno',
        manual_parameters=[
            openapi.Parameter('alumno_id', openapi.IN_QUERY, description='ID del alumno', type=openapi.TYPE_INTEGER)
        ],
        responses={200: CalificacionesSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def por_alumno(self, request):
        alumno_id = request.query_params.get('alumno_id')
        if not alumno_id:
            return Response({'error': 'Parámetro alumno_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)

        calificaciones = Calificaciones.objects.filter(inscripcion__alumno_id=alumno_id)
        serializer = self.get_serializer(calificaciones, many=True)
        return Response(serializer.data)

@swagger_auto_schema(tags=['Asistencias'])
class AsistenciasViewSet(viewsets.ModelViewSet):
    queryset = Asistencias.objects.select_related('alumno', 'grupo', 'grupo__grado', 'grupo__seccion', 'profesor_registro')
    serializer_class = AsistenciasSerializer
    permission_classes = [EsProfesorOAdmin]
    filterset_fields = ['fecha', 'alumno', 'grupo', 'estado']
    search_fields = ['alumno__primer_nombre', 'alumno__primer_apellido', 'alumno__cedula_escolar']

    def get_queryset(self):
        """
        Filtrado manual por query params (django-filter NO está disponible; restricción del proyecto):
        GET /api/academico/asistencias/?fecha=YYYY-MM-DD&grupo=<id>&estado=P&alumno=<id>

        - Paginación deshabilitada: al filtrar por grupo/fecha se retorna el listado
          completo en un solo paso (los grupos tardan 35-40 alumnos, sin necesidad de páginas).
        - Valores inválidos se ignoran limpiamente para no romper la BD legacy.
        - select_related('alumno', 'grupo') elimina las consultas N+1 al serializar.
        """
        qs = super().get_queryset()

        # --- Paginación: ignorar cualquier paginación global y devolver el listado completo ---
        self.pagination_class = None

        params = self.request.query_params

        # --- fecha (YYYY-MM-DD) ---
        fecha = (params.get('fecha') or '').strip()
        if fecha:
            try:
                datetime.strptime(fecha, '%Y-%m-%d')
            except ValueError:
                fecha = ''  # formato inválido -> se ignora limpiamente
        if fecha:
            qs = qs.filter(fecha=fecha)

        # --- grupo / alumno (enteros) ---
        for param, campo in (('grupo', 'grupo_id'), ('alumno', 'alumno_id')):
            valor = (params.get(param) or '').strip()
            if valor:
                try:
                    qs = qs.filter(**{campo: int(valor)})
                except (ValueError, TypeError):
                    pass  # no numérico -> se ignora limpiamente

        # --- estado (solo P/A/J válidos) ---
        estado = (params.get('estado') or '').strip().upper()
        estados_validos = {codigo for codigo, _ in Asistencias.ESTADO_CHOICES}
        if estado in estados_validos:
            qs = qs.filter(estado=estado)

        # --- Optimización N+1: carga directa de alumno y grupo (extra: grado/seccion/profesor) ---
        qs = qs.select_related('alumno', 'grupo')

        return qs


    @swagger_auto_schema(
        operation_description='Obtener estadísticas de asistencia por grupo',
        manual_parameters=[
            openapi.Parameter('grupo_id', openapi.IN_QUERY, description='ID del grupo', type=openapi.TYPE_INTEGER),
            openapi.Parameter('fecha_inicio', openapi.IN_QUERY, description='Fecha inicio (YYYY-MM-DD)', type=openapi.TYPE_STRING),
            openapi.Parameter('fecha_fin', openapi.IN_QUERY, description='Fecha fin (YYYY-MM-DD)', type=openapi.TYPE_STRING),
        ],
        responses={200: openapi.Response('Estadísticas de asistencia')}
    )
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Obtiene estadísticas de asistencia para un grupo en un rango de fechas.
        Retorna: total_dias, presentes, ausentes, justificados, porcentaje_asistencia
        """
        grupo_id = request.query_params.get('grupo_id')
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')

        if not grupo_id:
            return Response({'error': 'Parámetro grupo_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.queryset.filter(grupo_id=grupo_id)

        if fecha_inicio:
            queryset = queryset.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__lte=fecha_fin)

        total_registros = queryset.count()
        if total_registros == 0:
            return Response({
                'mensaje': 'No hay registros de asistencia para este grupo en el rango de fechas',
                'estadisticas': {
                    'total_dias': 0,
                    'presentes': 0,
                    'ausentes': 0,
                    'justificados': 0,
                    'porcentaje_asistencia': 0
                }
            })

        presentes = queryset.filter(estado='P').count()
        ausentes = queryset.filter(estado='A').count()
        justificados = queryset.filter(estado='J').count()

        porcentaje_asistencia = round((presentes / total_registros) * 100, 2) if total_registros > 0 else 0

        return Response({
            'grupo_id': grupo_id,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'estadisticas': {
                'total_dias': total_registros,
                'presentes': presentes,
                'ausentes': ausentes,
                'justificados': justificados,
                'porcentaje_asistencia': porcentaje_asistencia
            }
        })

    @swagger_auto_schema(
        operation_description='Obtener estadísticas de asistencia por alumno',
        manual_parameters=[
            openapi.Parameter('alumno_id', openapi.IN_QUERY, description='ID del alumno', type=openapi.TYPE_INTEGER),
            openapi.Parameter('fecha_inicio', openapi.IN_QUERY, description='Fecha inicio (YYYY-MM-DD)', type=openapi.TYPE_STRING),
            openapi.Parameter('fecha_fin', openapi.IN_QUERY, description='Fecha fin (YYYY-MM-DD)', type=openapi.TYPE_STRING),
        ],
        responses={200: openapi.Response('Estadísticas de asistencia por alumno')}
    )
    @action(detail=False, methods=['get'])
    def estadisticas_alumno(self, request):
        alumno_id = request.query_params.get('alumno_id')
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')

        if not alumno_id:
            return Response({'error': 'Parámetro alumno_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.queryset.filter(alumno_id=alumno_id)

        if fecha_inicio:
            queryset = queryset.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__lte=fecha_fin)

        total_registros = queryset.count()
        if total_registros == 0:
            return Response({
                'mensaje': 'No hay registros de asistencia para este alumno',
                'estadisticas': {
                    'total_dias': 0,
                    'presentes': 0,
                    'ausentes': 0,
                    'justificados': 0,
                    'porcentaje_asistencia': 0
                }
            })

        presentes = queryset.filter(estado='P').count()
        ausentes = queryset.filter(estado='A').count()
        justificados = queryset.filter(estado='J').count()

        porcentaje_asistencia = round((presentes / total_registros) * 100, 2) if total_registros > 0 else 0

        return Response({
            'alumno_id': alumno_id,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'estadisticas': {
                'total_dias': total_registros,
                'presentes': presentes,
                'ausentes': ausentes,
                'justificados': justificados,
                'porcentaje_asistencia': porcentaje_asistencia
            }
        })

@swagger_auto_schema(
    method='GET',
    operation_description='Exportar asistencias en formato CSV',
    tags=['Exportaciones Asistencias'],
    manual_parameters=[
        openapi.Parameter('grupo_id', openapi.IN_QUERY, description='ID del grupo (opcional)', type=openapi.TYPE_INTEGER, required=False),
        openapi.Parameter('fecha_inicio', openapi.IN_QUERY, description='Fecha inicio (YYYY-MM-DD)', type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('fecha_fin', openapi.IN_QUERY, description='Fecha fin (YYYY-MM-DD)', type=openapi.TYPE_STRING, required=False),
    ],
    responses={200: openapi.Response('Archivo CSV')}
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def exportar_asistencias_csv(request):
    grupo_id = request.query_params.get('grupo_id')
    fecha_inicio = request.query_params.get('fecha_inicio')
    fecha_fin = request.query_params.get('fecha_fin')

    queryset = Asistencias.objects.select_related('alumno', 'grupo', 'grupo__grado', 'grupo__seccion')

    if grupo_id:
        queryset = queryset.filter(grupo_id=grupo_id)
    if fecha_inicio:
        queryset = queryset.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(fecha__lte=fecha_fin)

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

@swagger_auto_schema(
    method='GET',
    operation_description='Exportar asistencias en formato Excel',
    tags=['Exportaciones Asistencias'],
    manual_parameters=[
        openapi.Parameter('grupo_id', openapi.IN_QUERY, description='ID del grupo (opcional)', type=openapi.TYPE_INTEGER, required=False),
        openapi.Parameter('fecha_inicio', openapi.IN_QUERY, description='Fecha inicio (YYYY-MM-DD)', type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('fecha_fin', openapi.IN_QUERY, description='Fecha fin (YYYY-MM-DD)', type=openapi.TYPE_STRING, required=False),
    ],
    responses={200: openapi.Response('Archivo Excel')}
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def exportar_asistencias_excel(request):
    grupo_id = request.query_params.get('grupo_id')
    fecha_inicio = request.query_params.get('fecha_inicio')
    fecha_fin = request.query_params.get('fecha_fin')

    queryset = Asistencias.objects.select_related('alumno', 'grupo', 'grupo__grado', 'grupo__seccion')

    if grupo_id:
        queryset = queryset.filter(grupo_id=grupo_id)
    if fecha_inicio:
        queryset = queryset.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(fecha__lte=fecha_fin)

    wb = openpyxl.Workbook()
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

@swagger_auto_schema(
    method='GET',
    operation_description='Exportar asistencias en formato PDF',
    tags=['Exportaciones Asistencias'],
    manual_parameters=[
        openapi.Parameter('grupo_id', openapi.IN_QUERY, description='ID del grupo (opcional)', type=openapi.TYPE_INTEGER, required=False),
        openapi.Parameter('fecha_inicio', openapi.IN_QUERY, description='Fecha inicio (YYYY-MM-DD)', type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('fecha_fin', openapi.IN_QUERY, description='Fecha fin (YYYY-MM-DD)', type=openapi.TYPE_STRING, required=False),
    ],
    responses={200: openapi.Response('Archivo PDF')}
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def exportar_asistencias_pdf(request):
    grupo_id = request.query_params.get('grupo_id')
    fecha_inicio = request.query_params.get('fecha_inicio')
    fecha_fin = request.query_params.get('fecha_fin')

    queryset = Asistencias.objects.select_related('alumno', 'grupo', 'grupo__grado', 'grupo__seccion')

    if grupo_id:
        queryset = queryset.filter(grupo_id=grupo_id)
    if fecha_inicio:
        queryset = queryset.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(fecha__lte=fecha_fin)

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
            fontSize=10, leading=14, textColor=colors.HexColor('#4A5568')
        ),
    }


def _texto_seguro(valor, defecto='N/A'):
    """Convierte un valor a texto escapado para usarlo dentro de un Paragraph de ReportLab."""
    if valor is None or valor == '':
        return escape(defecto)
    return escape(str(valor))


def _tabla_clave_valor(filas, estilos):
    """
    Construye una tabla de dos columnas (etiqueta / valor).
    Los valores se envuelven en Paragraph para que los textos largos se ajusten a la celda;
    se escapan porque provienen de datos externos (webhook de Google Forms).
    """
    datos = [
        [Paragraph(escape(etiqueta), estilos['label']), Paragraph(valor, estilos['normal'])]
        for etiqueta, valor in filas
    ]
    tabla = Table(datos, colWidths=[150, 362])
    tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#F7FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#CBD5E0')),
    ]))
    return tabla


@swagger_auto_schema(
    method='GET',
    operation_description='Generar comprobante de inscripción en PDF',
    tags=['Inscripciones'],
    responses={200: openapi.Response('Archivo PDF'), 404: openapi.Response('Inscripción no encontrada')}
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def generar_comprobante_inscripcion_pdf(request, inscripcion_id):
    """
    Genera el comprobante de inscripción en PDF de un alumno.
    Incluye datos del plantel, datos personales, tallas de uniforme, datos médicos,
    grupo académico asignado y datos de la inscripción.
    Ejemplo: GET /api/academico/inscripciones/{id}/pdf/
    """
    try:
        inscripcion = Inscripciones.objects.select_related(
            'alumno', 'grupo', 'grupo__periodo', 'grupo__nivel',
            'grupo__grado', 'grupo__seccion', 'grupo__turno'
        ).get(id_inscripcion=inscripcion_id)
    except Inscripciones.DoesNotExist:
        return Response({'error': 'Inscripción no encontrada'}, status=status.HTTP_404_NOT_FOUND)

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
        return Response(
            {'error': 'Error al generar el comprobante de inscripción'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@swagger_auto_schema(
    method='POST',
    operation_description='Webhook para recibir datos de Google Forms',
    tags=['Webhook'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'primer_nombre': openapi.Schema(type=openapi.TYPE_STRING),
            'segundo_nombre': openapi.Schema(type=openapi.TYPE_STRING),
            'primer_apellido': openapi.Schema(type=openapi.TYPE_STRING),
            'segundo_apellido': openapi.Schema(type=openapi.TYPE_STRING),
            'tipo_documento_identidad': openapi.Schema(type=openapi.TYPE_STRING),
            'numero_documento_identidad': openapi.Schema(type=openapi.TYPE_STRING),
            'cedula_escolar': openapi.Schema(type=openapi.TYPE_STRING),
            'fecha_nacimiento': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
            'genero': openapi.Schema(type=openapi.TYPE_STRING),
            'nacionalidad': openapi.Schema(type=openapi.TYPE_STRING),
            'lugar_nacimiento': openapi.Schema(type=openapi.TYPE_STRING),
            'grupo_sanguineo': openapi.Schema(type=openapi.TYPE_STRING),
            'peso_kg': openapi.Schema(type=openapi.TYPE_NUMBER),
            'talla_cm': openapi.Schema(type=openapi.TYPE_NUMBER),
            'talla_camisa': openapi.Schema(type=openapi.TYPE_STRING),
            'talla_pantalon': openapi.Schema(type=openapi.TYPE_STRING),
            'talla_zapato': openapi.Schema(type=openapi.TYPE_STRING),
            'alergico_a': openapi.Schema(type=openapi.TYPE_STRING),
            'tratamiento_medico': openapi.Schema(type=openapi.TYPE_STRING),
            'condicion_fisica': openapi.Schema(type=openapi.TYPE_STRING),
            'discapacidad': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            'tipo_discapacidad': openapi.Schema(type=openapi.TYPE_STRING),
            'id_grupo': openapi.Schema(type=openapi.TYPE_INTEGER),
            'monto_pago': openapi.Schema(type=openapi.TYPE_NUMBER),
            'referencia_bancaria': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['primer_nombre', 'primer_apellido', 'numero_documento_identidad', 'cedula_escolar', 'fecha_nacimiento']
    ),
    responses={201: openapi.Response('Alumno creado exitosamente'), 400: openapi.Response('Error de validación')}
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def webhook_google_forms(request):
    """
    Webhook para recibir datos de Google Forms/Google Apps Script.
    Crea automáticamente un alumno y opcionalmente su inscripción.
    """
    # Validar token de seguridad (comparación en tiempo constante para evitar timing attacks).
    # Si el servidor no tiene token configurado, el webhook queda cerrado.
    token_esperado = getattr(settings, 'WEBHOOK_SECRET_TOKEN', '') or ''
    token_recibido = request.headers.get('X-Webhook-Token', '')
    if not token_esperado or not hmac.compare_digest(
        token_recibido.encode('utf-8'), token_esperado.encode('utf-8')
    ):
        return Response(
            {'error': 'Token de seguridad inválido o no proporcionado'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        data = request.data
        
        # Validar campos requeridos
        campos_requeridos = ['primer_nombre', 'primer_apellido', 'numero_documento_identidad', 'cedula_escolar', 'fecha_nacimiento']
        for campo in campos_requeridos:
            if campo not in data or not data[campo]:
                return Response(
                    {'error': f'El campo {campo} es requerido'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Verificar si ya existe un alumno con el mismo número de documento
        if Alumnos.objects.filter(numero_documento_identidad=data['numero_documento_identidad']).exists():
            return Response(
                {'error': 'Ya existe un alumno con este número de documento'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar si ya existe un alumno con la misma cédula escolar
        if data.get('cedula_escolar') and Alumnos.objects.filter(cedula_escolar=data['cedula_escolar']).exists():
            return Response(
                {'error': 'Ya existe un alumno con esta cédula escolar'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
        
        alumno = Alumnos.objects.create(**alumno_data)
        
        # Si se incluye id_grupo, crear la inscripción
        inscripcion = None
        if data.get('id_grupo'):
            try:
                grupo = GruposAcademicos.objects.get(id_grupo=data['id_grupo'])
                from datetime import datetime
                inscripcion_data = {
                    'alumno': alumno,
                    'grupo': grupo,
                    'fecha_inscripcion': data.get('fecha_inscripcion') or datetime.now(),
                    'estado_inscripcion': data.get('estado_inscripcion', 'Activa'),
                    'monto_pago': data.get('monto_pago'),
                    'referencia_bancaria': data.get('referencia_bancaria')
                }
                inscripcion = Inscripciones.objects.create(**inscripcion_data)
            except GruposAcademicos.DoesNotExist:
                return Response(
                    {'error': 'El grupo especificado no existe', 'alumno_id': alumno.id_alumno},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response({
            'success': True,
            'message': 'Alumno creado exitosamente',
            'alumno_id': alumno.id_alumno,
            'inscripcion_id': inscripcion.id_inscripcion if inscripcion else None
        }, status=status.HTTP_201_CREATED)
        
    except Exception:
        logger.exception('Error al procesar la solicitud del webhook de Google Forms')
        return Response(
            {'error': 'Error al procesar la solicitud'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
