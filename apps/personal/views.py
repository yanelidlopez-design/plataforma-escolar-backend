from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes, action
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import HttpResponse
import csv
import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from .models import Profesores, RepresentantesLegales, AlumnoRepresentante
from .serializers import ProfesoresSerializer, RepresentantesLegalesSerializer, AlumnoRepresentanteSerializer

@swagger_auto_schema(tags=['Profesores'])
class ProfesoresViewSet(viewsets.ModelViewSet):
    queryset = Profesores.objects.select_related('id_usuario').all()
    serializer_class = ProfesoresSerializer
    search_fields = ['cedula', 'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido', 'especialidad']

    @swagger_auto_schema(
        method='GET',
        operation_description='Exportar personal con cargos en formato Excel (.xlsx)',
        responses={200: openapi.Response('Archivo Excel')}
    )
    @action(detail=False, methods=['get'], url_path='exportar-excel')
    def exportar_excel(self, request):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Personal con Cargos"

        fuente_cabecera = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        relleno_azul = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")

        encabezados = ['Cédula', 'Primer Nombre', 'Primer Apellido', 'Especialidad', 'Cargo', 'Teléfono', 'Correo']
        ws.append(encabezados)

        for col_num in range(1, len(encabezados) + 1):
            celda = ws.cell(row=1, column=col_num)
            celda.font = fuente_cabecera
            celda.fill = relleno_azul

        personal = self.get_queryset()

        for p in personal:
            cargo = getattr(p, 'cargo', 'No asignado')
            telefono = getattr(p, 'telefono', '') or (getattr(p.id_usuario, 'telefono', 'No registrado') if p.id_usuario else 'No registrado')
            correo = getattr(p, 'correo', '') or (getattr(p.id_usuario, 'email', 'No registrado') if p.id_usuario else 'No registrado')

            ws.append([
                p.cedula,
                p.primer_nombre,
                p.primer_apellido,
                p.especialidad or 'No especificada',
                cargo,
                telefono,
                correo
            ])

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="personal_con_cargos.xlsx"'

        wb.save(response)
        return response

@swagger_auto_schema(tags=['Representantes Legales'])
class RepresentantesLegalesViewSet(viewsets.ModelViewSet):
    queryset = RepresentantesLegales.objects.select_related('id_direccion_residencia').all()
    serializer_class = RepresentantesLegalesSerializer
    search_fields = ['cedula', 'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido']

@swagger_auto_schema(tags=['Alumno-Representante'])
class AlumnoRepresentanteViewSet(viewsets.ModelViewSet):
    queryset = AlumnoRepresentante.objects.all()
    serializer_class = AlumnoRepresentanteSerializer
    filterset_fields = ['id_alumno', 'id_representante', 'es_principal']

@swagger_auto_schema(
    method='GET',
    operation_description='Exportar alumnos y representantes en formato CSV',
    tags=['Exportaciones'],
    responses={200: openapi.Response('Archivo CSV')}
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def exportar_alumnos_representantes_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="alumnos_y_representantes.csv"'

    writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['Alumno', 'Representante', 'Teléfono', 'Parentesco', 'Es Principal'])

    relaciones = AlumnoRepresentante.objects.select_related('alumno', 'representante')

    for relacion in relaciones:
       writer.writerow([
           f"{relacion.alumno.primer_nombre} {relacion.alumno.primer_apellido}",
           f"{relacion.representante.primer_nombre} {relacion.representante.primer_apellido}",
           relacion.representante.telefono_principal or 'No registrado',
           relacion.parentesco or 'No especificado',
           'Sí' if relacion.es_principal else 'No'
       ])

    return response

@swagger_auto_schema(
    method='GET',
    operation_description='Exportar alumnos y representantes en formato Excel',
    tags=['Exportaciones'],
    responses={200: openapi.Response('Archivo Excel')}
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def exportar_alumnos_representantes_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Alumnos y Representantes"

    fuente_titulo = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    relleno_azul = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")

    encabezados = ['Alumno', 'Representante', 'Teléfono', 'Parentesco', 'Es Principal']
    ws.append(encabezados)

    for col_num in range(1, 6):
        celda = ws.cell(row=1, column=col_num)
        celda.font = fuente_titulo
        celda.fill = relleno_azul

    relaciones = AlumnoRepresentante.objects.select_related('alumno', 'representante')

    for relacion in relaciones:
        ws.append([
            f"{relacion.alumno.primer_nombre} {relacion.alumno.primer_apellido}",
            f"{relacion.representante.primer_nombre} {relacion.representante.primer_apellido}",
            relacion.representante.telefono_principal or 'No registrado',
            relacion.parentesco or 'No especificado',
            "Sí" if relacion.es_principal else "No"
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="reporte_institucional.xlsx"'

    wb.save(response)
    return response

@swagger_auto_schema(
    method='GET',
    operation_description='Exportar alumnos y representantes en formato PDF',
    tags=['Exportaciones'],
    responses={200: openapi.Response('Archivo PDF')}
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def exportar_alumnos_representantes_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="lista_alumnos.pdf"'

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

    story.append(Paragraph("PLATAFORMA ESCOLAR - CONTROL DE INSCRIPCIONES", estilo_titulo))
    story.append(Spacer(1, 20))

    datos_tabla = [['Alumno', 'Representante', 'Teléfono', 'Parentesco', 'Es Principal']]

    relaciones = AlumnoRepresentante.objects.select_related('alumno', 'representante')
    for relacion in relaciones:
        datos_tabla.append([
            f"{relacion.alumno.primer_nombre} {relacion.alumno.primer_apellido}",
            f"{relacion.representante.primer_nombre} {relacion.representante.primer_apellido}",
            relacion.representante.telefono_principal or 'No registrado',
            relacion.parentesco or 'No especificado',
            "Principal" if relacion.es_principal else "Secundario"
        ])

    tabla_pdf = Table(datos_tabla, colWidths=[150, 150, 120, 100, 100])
    tabla_pdf.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E78')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F2F4F7')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')])
    ]))

    story.append(tabla_pdf)

    doc.build(story)
    return response
