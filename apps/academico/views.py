from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import HttpResponse
from django.conf import settings
from django.utils import timezone
from django.db import IntegrityError
from django.db.models import ProtectedError
import csv
import hmac
import logging
import re
from xml.sax.saxutils import escape
import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import letter, landscape
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
from apps.core.models import ConfiguracionPlantel, GradosAcademicos, Secciones
from apps.core.serializers import GradosAcademicosSerializer, SeccionesSerializer

logger = logging.getLogger(__name__)

@swagger_auto_schema(tags=['Alumnos'])
class AlumnosViewSet(viewsets.ModelViewSet):
    queryset = Alumnos.objects.select_related('id_direccion_residencia', 'id_profesor_encargado').prefetch_related('representantes_vinculados')
    serializer_class = AlumnosSerializer
    permission_classes = [EsProfesorOAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['cedula_escolar', 'numero_documento_identidad', 'primer_nombre', 'primer_apellido']
    ordering_fields = ['primer_apellido', 'primer_nombre']
    filter_fields = ['grado', 'seccion', 'estado_inscripcion']

    # Encabezados únicos de las exportaciones (Excel/PDF/CSV) para que las 3
    # vistas compartan exactamente las mismas columnas.
    # Orden: identificación -> académico -> datos personales -> patria -> cuenta ->
    #        dirección -> representante (tipo/doc/teléfono) -> profesor.
    ALUMNOS_EXPORT_ENCABEZADOS = [
        'Cédula Escolar',
        'Tipo Documento', 'N° de Documento',
        'Nombre Completo', 'Fecha Nacimiento', 'Género',
        'Grado', 'Sección', 'Estado de Inscripción', 'Grupo Sanguíneo',
        'Carnet Patria Código', 'Carnet Patria Serial',
        'N° Cuenta', 'Tipo Cuenta', 'Banco',
        'Calle', 'Ciudad', 'Estado', 'Referencia',
        'Representante', 'Tipo Doc. Rep.', 'N° Doc. Rep.', 'Teléfono Rep.',
        'Profesor Encargado',
    ]

    # Subconjunto de columnas que se muestran en el PDF (datos principales).
    # El PDF con las 25 columnas resulta ilegible; aquí van las más relevantes.
    ALUMNOS_PDF_COLUMNAS = [
        'Cédula Escolar', 'Tipo Documento', 'N° de Documento', 'Nombre Completo',
        'Fecha Nacimiento', 'Género', 'Grado', 'Sección',
        'Estado de Inscripción', 'Representante', 'Teléfono Rep.', 'Profesor Encargado',
    ]

    @classmethod
    def _fila_alumno_pdf(cls, alumno):
        """Fila reducida (solo ALUMNOS_PDF_COLUMNAS) a partir de la fila completa."""
        fila = cls._fila_alumno(alumno)
        idx = [cls.ALUMNOS_EXPORT_ENCABEZADOS.index(c) for c in cls.ALUMNOS_PDF_COLUMNAS]
        return [fila[i] for i in idx]

    @classmethod
    def _fila_alumno(cls, alumno):
        """Construye una fila con el orden de ALUMNOS_EXPORT_ENCABEZADOS."""
        nombre_completo = ' '.join(filter(None, [
            alumno.primer_nombre or '',
            alumno.segundo_nombre or '',
            alumno.primer_apellido or '',
            alumno.segundo_apellido or ''
        ])).strip() or 'N/D'

        grado_nom, seccion_nom, estado_insc = cls._datos_academicos_alumno(alumno)

        direccion = alumno.id_direccion_residencia if hasattr(alumno, 'id_direccion_residencia') else None
        calle = direccion.calle if direccion and hasattr(direccion, 'calle') else ''
        ciudad = direccion.ciudad if direccion and hasattr(direccion, 'ciudad') else ''
        estado_ref = direccion.estado if direccion and hasattr(direccion, 'estado') else ''
        referencia = direccion.referencia if direccion and hasattr(direccion, 'referencia') else ''

        repre = cls._primera_relacion(alumno, 'representantes_vinculados')
        # representantes_vinculados devuelve el pivote AlumnoRepresentante; el
        # representante real (con nombres, cédula y teléfono) está en .representante.
        repre_real = getattr(repre, 'representante', None) if repre else None
        representante_nom = 'N/D'
        repre_tipo_doc = 'N/D'
        repre_num_doc = 'N/D'
        repre_telefono = 'N/D'
        if repre_real:
            representante_nom = ' '.join(filter(None, [
                getattr(repre_real, 'primer_nombre', ''), getattr(repre_real, 'segundo_nombre', ''),
                getattr(repre_real, 'primer_apellido', ''), getattr(repre_real, 'segundo_apellido', '')
            ])).strip() or 'N/D'
            repre_tipo_doc, repre_num_doc = _separar_documento(getattr(repre_real, 'cedula', None))
            repre_telefono = getattr(repre_real, 'telefono_principal', None) or 'N/D'

        fecha_nac = getattr(alumno, 'fecha_nacimiento', None)
        fecha_nac_str = fecha_nac.strftime('%d/%m/%Y') if hasattr(fecha_nac, 'strftime') else str(fecha_nac or 'N/D')

        return [
            alumno.cedula_escolar or 'N/D',
            alumno.tipo_documento_identidad or 'N/D',
            alumno.numero_documento_identidad or 'N/D',
            nombre_completo,
            fecha_nac_str,
            alumno.genero or 'N/D',
            grado_nom,
            seccion_nom,
            estado_insc,
            alumno.grupo_sanguineo or 'N/D',
            alumno.carnet_patria_codigo or 'N/D',
            alumno.carnet_patria_serial or 'N/D',
            alumno.numero_cuenta or 'N/D',
            alumno.tipo_cuenta or 'N/D',
            alumno.banco or 'N/D',
            calle or 'N/D',
            ciudad or 'N/D',
            estado_ref or 'N/D',
            referencia or 'N/D',
            representante_nom or 'N/D',
            repre_tipo_doc,
            repre_num_doc,
            repre_telefono,
            cls._obtener_nombre_y_apellido(alumno.id_profesor_encargado) if getattr(alumno, 'id_profesor_encargado', None) else 'N/D',
        ]

    def get_queryset(self):
        """Listado base de alumnos con filtros opcionales por grado y sección."""
        qs = super().get_queryset()

        # Filtros manuales (django-filter no está instalado en el proyecto)
        grado_id = self.request.query_params.get('grado')
        seccion_id = self.request.query_params.get('seccion')
        estado = self.request.query_params.get('estado')

        if grado_id or seccion_id or estado:
            # Construcción del filtrado a través de Inscripciones y GruposAcademicos
            try:
                inscripciones = Inscripciones.objects.all()
                if grado_id:
                    # Acepta ID numérico (backend real) o nombre de grado (fallback offline del frontend)
                    if str(grado_id).isdigit():
                        inscripciones = inscripciones.filter(grupo__grado_id=int(grado_id))
                    else:
                        inscripciones = inscripciones.filter(grupo__grado__nombre_grado=str(grado_id))
                if seccion_id:
                    if str(seccion_id).isdigit():
                        inscripciones = inscripciones.filter(grupo__seccion_id=int(seccion_id))
                    else:
                        inscripciones = inscripciones.filter(grupo__seccion__nombre_seccion=str(seccion_id))
                if estado:
                    inscripciones = inscripciones.filter(estado_inscripcion=estado)
                alumno_ids = list(inscripciones.values_list('alumno_id', flat=True).distinct())
            except (ValueError, TypeError, OverflowError):
                # Valores inválidos → devolver todos los alumnos
                alumno_ids = []

            if alumno_ids:
                qs = qs.filter(id_alumno__in=alumno_ids)

        # Optimizamos las relaciones necesarias para serialización y display.
        # OJO: 'representantes_vinculados' es una relación inversa (1:N); NO puede ir
        # en select_related porque el JOIN multiplica filas (alumnos duplicados en la lista).
        # Se maneja con prefetch_related en el queryset base del ViewSet.
        qs = qs.select_related('id_direccion_residencia')

        return qs

    @staticmethod
    def _datos_academicos_alumno(alumno):
        """(Grado, Sección, Estado de inscripción) del alumno.

        El modelo Alumnos NO tiene FK directa de grado/sección: se resuelven
        a través de su inscripción activa (o la primera disponible).
        """
        try:
            inscripcion = (
                alumno.inscripciones.filter(estado_inscripcion='Activa').first()
                or alumno.inscripciones.first()
            )
        except Exception:
            inscripcion = None
        if not inscripcion or not inscripcion.grupo:
            return 'N/D', 'N/D', 'N/D'
        grupo = inscripcion.grupo
        return (
            grupo.grado.nombre_grado if grupo.grado_id else 'N/D',
            grupo.seccion.nombre_seccion if grupo.seccion_id else 'N/D',
            inscripcion.estado_inscripcion or 'N/D',
        )

    def destroy(self, request, *args, **kwargs):
        """
        Eliminación en cascada: inscripciones -> calificaciones, asistencias y
        vínculos con representantes (alineado con las FKs legacy CASCADE).
        Si la BD lo impide, responde 409 con mensaje claro en vez de 500 con HTML.
        """
        try:
            return super().destroy(request, *args, **kwargs)
        except (ProtectedError, IntegrityError) as exc:
            logger.warning('No se pudo eliminar el alumno pk=%s: %s', kwargs.get('pk'), exc)
            return Response(
                {'detail': 'No se puede eliminar: el alumno tiene inscripciones o registros asociados.'},
                status=status.HTTP_409_CONFLICT,
            )

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


    @swagger_auto_schema(
        method='GET',
        operation_description='Exportar alumnos en formato Excel (.xlsx), respetando los filtros grado/seccion',
        tags=['Exportaciones Alumnos'],
        manual_parameters=[
            openapi.Parameter('grado', openapi.IN_QUERY, description='ID del grado (opcional)', type=openapi.TYPE_INTEGER),
            openapi.Parameter('seccion', openapi.IN_QUERY, description='ID de la sección (opcional)', type=openapi.TYPE_INTEGER),
            openapi.Parameter('estado', openapi.IN_QUERY, description='Estado de inscripción (opcional)', type=openapi.TYPE_STRING),
        ],
        responses={200: openapi.Response('Archivo Excel'), 400: openapi.Response('Solicitud inválida')}
    )

    @action(detail=False, methods=['get'], url_path='exportar-alumnos-excel')
    def exportar_alumnos_excel(self, request):
        """Exportar a Excel los alumnos filtrados por grado/seccion/estado."""
        grado_id = request.query_params.get('grado')
        seccion_id = request.query_params.get('seccion')
        estado = request.query_params.get('estado')

        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay alumnos que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Alumnos"

        fuente_cabecera = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        relleno_azul = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")

        ws.append(self.ALUMNOS_EXPORT_ENCABEZADOS)

        for col_num in range(1, len(self.ALUMNOS_EXPORT_ENCABEZADOS) + 1):
            celda = ws.cell(row=1, column=col_num)
            celda.font = fuente_cabecera
            celda.fill = relleno_azul

        for alumno in qs:
            ws.append(self._fila_alumno(alumno))

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

    @swagger_auto_schema(
        method='GET',
        operation_description='Exportar alumnos en formato PDF, respetando los filtros grado/seccion/estado',
        tags=['Exportaciones Alumnos'],
        manual_parameters=[
            openapi.Parameter('grado', openapi.IN_QUERY, description='ID del grado (opcional)', type=openapi.TYPE_INTEGER),
            openapi.Parameter('seccion', openapi.IN_QUERY, description='ID de la sección (opcional)', type=openapi.TYPE_INTEGER),
            openapi.Parameter('estado', openapi.IN_QUERY, description='Estado de inscripción (opcional)', type=openapi.TYPE_STRING),
        ],
        responses={200: openapi.Response('Archivo PDF'), 400: openapi.Response('Solicitud inválida')}
    )
    @action(detail=False, methods=['get'], url_path='exportar-alumnos-pdf')
    def exportar_alumnos_pdf(self, request):
        """Exportar a PDF los alumnos filtrados por grado/seccion/estado."""
        grado_id = request.query_params.get('grado')
        seccion_id = request.query_params.get('seccion')
        estado = request.query_params.get('estado')

        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay alumnos que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="alumnos.pdf"'

        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

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
                nombre_grado_f = GradosAcademicos.objects.filter(
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

        # PDF solo con datos principales (ALUMNOS_PDF_COLUMNAS) para que sea legible.
        # Portrait letter: 612 - 80 márgenes = 532pt útiles; los pesos se escalan
        # a ese ancho para que la tabla no se desborde.
        encabezados = self.ALUMNOS_PDF_COLUMNAS
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
        for alumno in qs:
            datos_tabla.append([
                Paragraph(_texto_seguro(valor, 'N/D'), estilo_celda)
                for valor in self._fila_alumno_pdf(alumno)
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

    @action(detail=False, methods=['get'], url_path='exportar-alumnos-csv')
    def exportar_alumnos_csv(self, request):
        """Exportar a CSV los alumnos filtrados por grado/seccion/estado (get_queryset)."""
        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay alumnos que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="alumnos.csv"'
        response.write('\ufeff')  # BOM UTF-8 para que Excel lo abra con acentos correctos

        writer = csv.writer(response)
        writer.writerow(self.ALUMNOS_EXPORT_ENCABEZADOS)

        for alumno in qs:
            writer.writerow(self._fila_alumno(alumno))

        return response


    @staticmethod
    def _primera_relacion(objeto, relacion):
        """Devuelve la primera instancia de una relación ManyRelatedManager, o None."""
        relacionador = getattr(objeto, relacion, None)
        if relacionador is None:
            return None
        try:
            return next(iter(relacionador.all()), None)
        except Exception:
            return None

    @staticmethod
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

    @swagger_auto_schema(
        method='GET',
        operation_description='Listar grados académicos',
        tags=['Grados'],
        responses={200: openapi.Response('Lista de grados')}
    )
    @action(detail=False, methods=['get'], url_path='grados')
    def list_grados(self, request):
        """Obtener la lista de grados disponibles."""
        qs = GradosAcademicos.objects.all()
        serializer = GradosAcademicosSerializer(qs, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='GET',
        operation_description='Listar secciones',
        tags=['Secciones'],
        responses={200: openapi.Response('Lista de secciones')}
    )
    @action(detail=False, methods=['get'], url_path='secciones')
    def list_secciones(self, request):
        """Obtener la lista de secciones disponibles."""
        qs = Secciones.objects.all()
        serializer = SeccionesSerializer(qs, many=True)
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
    queryset = Inscripciones.objects.select_related(
        'alumno', 'grupo', 'grupo__periodo', 'grupo__grado', 'grupo__seccion', 'grupo__turno'
    )
    serializer_class = InscripcionesSerializer
    permission_classes = [EsProfesorOAdmin]
    filterset_fields = ['estado_inscripcion', 'alumno', 'grupo']
    search_fields = ['alumno__primer_nombre', 'alumno__primer_apellido', 'alumno__cedula_escolar']

    # Cabeceras comunes de las exportaciones (Excel/PDF/CSV).
    EXPORT_ENCABEZADOS = [
        'Alumno', 'Tipo Documento', 'N° de Documento', 'Género', 'Fecha Nacimiento',
        'Grado', 'Sección', 'Turno', 'Docente Encargado',
        'Fecha Inscripción', 'Estado', 'Monto', 'Referencia Bancaria',
        'Dirección', 'Ciudad/Estado',
        'Representante', 'Tipo Doc. Rep.', 'N° Doc. Rep.', 'Teléfono Rep.',
        'Carnet Patria Código', 'Carnet Patria Serial',
        'N° Cuenta', 'Tipo Cuenta', 'Banco'
    ]

    # Subconjunto de columnas que se muestran en el PDF (datos principales).
    PDF_COLUMNAS = [
        'Alumno', 'Tipo Documento', 'N° de Documento',
        'Grado', 'Sección', 'Turno', 'Docente Encargado',
        'Fecha Inscripción', 'Estado', 'Monto', 'Referencia Bancaria',
        'Representante', 'Teléfono Rep.',
    ]

    @classmethod
    def _fila_inscripcion_pdf(cls, inscripcion):
        """Fila reducida (solo PDF_COLUMNAS) a partir de la fila completa."""
        fila = cls._fila_inscripcion(inscripcion)
        idx = [cls.EXPORT_ENCABEZADOS.index(c) for c in cls.PDF_COLUMNAS]
        return [fila[i] for i in idx]

    def get_queryset(self):
        """Filtrado manual (django-filter NO está disponible en el proyecto):
        GET /api/academico/inscripciones/?grado=<id|nombre>&seccion=<id|nombre>
                                &estado_inscripcion=<estado>&search=<texto>
        Valores vacíos = "Todos" (sin filtro)."""
        qs = super().get_queryset()
        params = self.request.query_params

        grado = (params.get('grado') or '').strip()
        if grado:
            if grado.isdigit():
                qs = qs.filter(grupo__grado_id=int(grado))
            else:
                qs = qs.filter(grupo__grado__nombre_grado=grado)

        seccion = (params.get('seccion') or '').strip()
        if seccion:
            if seccion.isdigit():
                qs = qs.filter(grupo__seccion_id=int(seccion))
            else:
                qs = qs.filter(grupo__seccion__nombre_seccion=seccion)

        estado = (params.get('estado_inscripcion') or '').strip()
        if estado:
            qs = qs.filter(estado_inscripcion=estado)

        search = (params.get('search') or '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(alumno__primer_nombre__icontains=search)
                | Q(alumno__primer_apellido__icontains=search)
                | Q(alumno__cedula_escolar__icontains=search)
                | Q(alumno__numero_documento_identidad__icontains=search)
            )

        return qs

    @staticmethod
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

    @staticmethod
    def _fila_inscripcion(inscripcion):
        """Fila común para Excel/PDF/CSV de una inscripción."""
        alumno = inscripcion.alumno
        grupo = inscripcion.grupo
        fecha = getattr(inscripcion, 'fecha_inscripcion', None)
        # Fecha legible dd/mm/aaaa (viene como datetime con zona horaria de la BD legacy).
        fecha_txt = fecha.strftime('%d/%m/%Y') if hasattr(fecha, 'strftime') else str(fecha or 'N/D')

        direccion = alumno.id_direccion_residencia if hasattr(alumno, 'id_direccion_residencia') else None
        calle = direccion.calle if direccion and hasattr(direccion, 'calle') else ''
        ciudad = direccion.ciudad if direccion and hasattr(direccion, 'ciudad') else ''
        estado_ref = direccion.estado if direccion and hasattr(direccion, 'estado') else ''
        referencia = direccion.referencia if direccion and hasattr(direccion, 'referencia') else ''

        pivote = alumno.representantes_vinculados.first() if hasattr(alumno, 'representantes_vinculados') else None
        # El pivote AlumnoRepresentante referencia al representante real en .representante.
        repre = getattr(pivote, 'representante', None) if pivote else None
        representante_nom = 'N/D'
        repre_tipo_doc = 'N/D'
        repre_num_doc = 'N/D'
        repre_telefono = 'N/D'
        if repre:
            representante_nom = ' '.join(filter(None, [
                getattr(repre, 'primer_nombre', ''), getattr(repre, 'segundo_nombre', ''),
                getattr(repre, 'primer_apellido', ''), getattr(repre, 'segundo_apellido', '')
            ])).strip() or 'N/D'
            repre_tipo_doc, repre_num_doc = _separar_documento(getattr(repre, 'cedula', None))
            repre_telefono = getattr(repre, 'telefono_principal', None) or 'N/D'

        fecha_nac = getattr(alumno, 'fecha_nacimiento', None)
        fecha_nac_str = fecha_nac.strftime('%d/%m/%Y') if hasattr(fecha_nac, 'strftime') else str(fecha_nac or 'N/D')

        return [
            ' '.join(filter(None, [
                getattr(alumno, 'primer_nombre', ''), getattr(alumno, 'segundo_nombre', ''),
                getattr(alumno, 'primer_apellido', ''), getattr(alumno, 'segundo_apellido', ''),
            ])).strip() or 'N/D',
            alumno.tipo_documento_identidad or 'N/D',
            alumno.numero_documento_identidad or alumno.cedula_escolar or 'N/D',
            alumno.genero or 'N/D',
            fecha_nac_str,
            grupo.grado.nombre_grado if grupo and grupo.grado_id else 'N/D',
            grupo.seccion.nombre_seccion if grupo and grupo.seccion_id else 'N/D',
            grupo.turno.nombre_turno if grupo and grupo.turno_id else 'N/D',
            InscripcionesViewSet._obtener_nombre_y_apellido(getattr(alumno, 'id_profesor_encargado', None))
            if hasattr(alumno, 'id_profesor_encargado') else 'N/D',
            fecha_txt,
            getattr(inscripcion, 'estado_inscripcion', '') or 'N/D',
            f"{float(getattr(inscripcion, 'monto_pago', None) or 0):.2f}",
            getattr(inscripcion, 'referencia_bancaria', None) or 'N/D',
            calle or 'N/D',
            f"{ciudad} {estado_ref}".strip() or 'N/D',
            representante_nom or 'N/D',
            repre_tipo_doc,
            repre_num_doc,
            repre_telefono,
            alumno.carnet_patria_codigo or 'N/D',
            alumno.carnet_patria_serial or 'N/D',
            alumno.numero_cuenta or 'N/D',
            alumno.tipo_cuenta or 'N/D',
            alumno.banco or 'N/D',
        ]

    @action(detail=False, methods=['get'], url_path='exportar-inscripciones-excel')
    def exportar_inscripciones_excel(self, request):
        """Exportar a Excel las inscripciones filtradas (grado/seccion/estado/search)."""
        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay inscripciones que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Inscripciones"

        fuente_cabecera = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        relleno_azul = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")

        ws.append(self.EXPORT_ENCABEZADOS)
        for col_num in range(1, len(self.EXPORT_ENCABEZADOS) + 1):
            celda = ws.cell(row=1, column=col_num)
            celda.font = fuente_cabecera
            celda.fill = relleno_azul

        for inscripcion in qs:
            ws.append(self._fila_inscripcion(inscripcion))

        for col in ws.columns:
            max_len = max(len(str(celda.value or '')) for celda in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 45)

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="inscripciones.xlsx"'
        wb.save(response)
        return response

    @action(detail=False, methods=['get'], url_path='exportar-inscripciones-pdf')
    def exportar_inscripciones_pdf(self, request):
        """Exportar a PDF las inscripciones filtradas (grado/seccion/estado/search)."""
        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay inscripciones que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

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
            valor = (request.query_params.get(param) or '').strip()
            if valor:
                filas_filtro.append((etiqueta, valor))
        if filas_filtro:
            story.append(Paragraph("FILTROS APLICADOS", estilo_subtitulo))
            story.append(_tabla_clave_valor(filas_filtro, styles))
            story.append(Spacer(1, 12))

        # PDF solo con datos principales (PDF_COLUMNAS) para que sea legible.
        # Landscape letter: 792 - 80 = 712pt útiles; los pesos se escalan a ese
        # ancho para que la tabla no se desborde.
        estilo_cab = ParagraphStyle(
            'PdfInsCab', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=7.5, leading=9, textColor=colors.white, alignment=1
        )
        estilo_celda = ParagraphStyle(
            'PdfInsCelda', parent=styles['Normal'], fontName='Helvetica',
            fontSize=7.5, leading=9
        )

        datos_tabla = [[Paragraph(escape(h), estilo_cab) for h in self.PDF_COLUMNAS]]
        for inscripcion in qs:
            datos_tabla.append([
                Paragraph(_texto_seguro(valor, 'N/D'), estilo_celda)
                for valor in self._fila_inscripcion_pdf(inscripcion)
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

    @action(detail=False, methods=['get'], url_path='exportar-inscripciones-csv')
    def exportar_inscripciones_csv(self, request):
        """Exportar a CSV las inscripciones filtradas (grado/seccion/estado/search)."""
        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay inscripciones que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="inscripciones.csv"'
        response.write('\ufeff')  # BOM UTF-8 para que Excel lo abra con acentos correctos

        writer = csv.writer(response)
        writer.writerow(self.EXPORT_ENCABEZADOS)
        for inscripcion in qs:
            writer.writerow(self._fila_inscripcion(inscripcion))

        return response


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


def _separar_documento(valor):
    """Separa un documento tipo 'V-8765432' en (tipo, número) = ('V', '8765432').

    Acepta formatos con guion, espacio o solo concatenado. Si no hay prefijo
    alfabético reconocible, devuelve ('N/D', número) para no perder el valor.
    """
    if valor is None or str(valor).strip() == '':
        return 'N/D', 'N/D'
    texto = str(valor).strip()
    # Separa en letras iniciales (tipo) y resto (número): 'V-123', 'E 123', '123'.
    match = re.match(r'^\s*([A-Za-z]{1,3})?[\s\-]*([0-9].*?)\s*$', texto)
    if match and match.group(1) and match.group(2):
        return match.group(1).upper(), match.group(2)
    if match and match.group(2):
        return 'N/D', match.group(2)
    return 'N/D', texto


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
    # Compatibilidad: getSampleStyleSheet() no trae las claves 'label'/'normal'
    # que espera esta tabla; se derivan automáticamente en ese caso (los
    # exportadores de PDF pasan la hoja estándar de ReportLab).
    try:
        etiqueta_estilo = estilos['label']
        valor_estilo = estilos['normal']
    except (KeyError, TypeError):
        etiqueta_estilo = ParagraphStyle(
            'FiltroLabel', parent=estilos['Normal'],
            fontName='Helvetica-Bold', fontSize=9, leading=11,
            textColor=colors.HexColor('#4A5568'),
        )
        valor_estilo = ParagraphStyle('FiltroNormal', parent=estilos['Normal'], fontSize=9, leading=11)

    datos = [
        [Paragraph(escape(str(etiqueta)), etiqueta_estilo), Paragraph(escape(str(valor)), valor_estilo)]
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
