from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import HttpResponse, FileResponse
from django.conf import settings
from django.utils import timezone
from django.db.models import ProtectedError, Prefetch
import logging
import re
from .models import Alumnos, GruposAcademicos, Inscripciones, Calificaciones, Asistencias, PeriodoInscripcion
from .serializers import (
    AlumnosSerializer, GruposAcademicosSerializer,
    InscripcionesSerializer, CalificacionesSerializer, AsistenciasSerializer,
    AlumnoInscripcionSerializer
)
from .permissions import EsProfesorOAdmin, EsAdministrador
from .decorators import validate_webhook_signature
from .reports import (
    exportar_alumnos_excel, exportar_alumnos_pdf, exportar_alumnos_csv,
    exportar_inscripciones_excel, exportar_inscripciones_pdf, exportar_inscripciones_csv,
    exportar_asistencias_excel, exportar_asistencias_pdf, exportar_asistencias_csv,
    ALUMNOS_EXPORT_ENCABEZADOS, ALUMNOS_PDF_COLUMNAS,
    INSCRIPCIONES_EXPORT_ENCABEZADOS, INSCRIPCIONES_PDF_COLUMNAS,
    _crear_estilos_comprobante, _separar_documento, _texto_seguro, _tabla_clave_valor
)
from .services.inscripcion_service import generar_comprobante_inscripcion
from .services.webhook_service import procesar_alumno_webhook, procesar_inscripcion_webhook
from .tasks import encolar_exportacion, leer_estado_reporte, ruta_archivo_reporte
from apps.core.models import ConfiguracionPlantel, GradosAcademicos, Secciones
from apps.core.serializers import GradosAcademicosSerializer, SeccionesSerializer

logger = logging.getLogger(__name__)


def _respuesta_reporte_encolado(modulo, formato, queryset):
    """Encola la generación del reporte en django-q2 y arma la respuesta 202."""
    reporte_id = encolar_exportacion(modulo, formato, queryset)
    return {
        'reporte_id': reporte_id,
        'estatus': 'Procesando',
        'url_estado': f'/api/academico/exports/{reporte_id}/',
        'url_descarga': f'/api/academico/exports/{reporte_id}/descarga/',
    }


@swagger_auto_schema(tags=['Alumnos'])
class AlumnosViewSet(viewsets.ModelViewSet):
    queryset = Alumnos.objects.all()
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
    ALUMNOS_EXPORT_ENCABEZADOS = ALUMNOS_EXPORT_ENCABEZADOS

    # Subconjunto de columnas que se muestran en el PDF (datos principales).
    # El PDF con las 25 columnas resulta ilegible; aquí van las más relevantes.
    ALUMNOS_PDF_COLUMNAS = ALUMNOS_PDF_COLUMNAS

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

        # Optimización N+1: precarga de relaciones para serialización
        # select_related: FK directas (1:1 o N:1)
        # prefetch_related: relaciones inversas o M:N
        # NOTA: grado/sección NO son FK directas de Alumnos (consolidación de
        # estudiantes); se resuelven vía Inscripciones -> grupo (prefetch abajo).
        qs = qs.select_related(
            'id_direccion_residencia',
            'id_profesor_encargado'
        ).prefetch_related(
            'representantes_vinculados__representante',  # Para to_representation()
            Prefetch(
                'inscripciones',
                queryset=Inscripciones.objects.select_related(
                    'grupo__grado',
                    'grupo__seccion',
                    'grupo__profesor_director'
                ).filter(estado_inscripcion__in=['Activa', 'Graduado'])
            )  # Para get_grado_actual, get_seccion_actual, get_profesor_encargado, get_grupo_inscripcion_id
        )

        return qs

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
        """Encolar exportación asíncrona a Excel (responde 202 con el reporte_id)."""
        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay alumnos que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            _respuesta_reporte_encolado('alumnos', 'excel', qs),
            status=status.HTTP_202_ACCEPTED
        )

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
        """Encolar exportación asíncrona a PDF (responde 202 con el reporte_id)."""
        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay alumnos que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            _respuesta_reporte_encolado('alumnos', 'pdf', qs),
            status=status.HTTP_202_ACCEPTED
        )

    @action(detail=False, methods=['get'], url_path='exportar-alumnos-csv')
    def exportar_alumnos_csv(self, request):
        """Exportar a CSV los alumnos filtrados por grado/seccion/estado (get_queryset)."""
        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay alumnos que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        response = exportar_alumnos_csv(qs)
        return response




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
        ).select_related(
            'alumno__id_direccion_residencia',
            'alumno__id_profesor_encargado'
        ).prefetch_related(
            'alumno__representantes_vinculados__representante',
            # grado/sección del alumno se resuelven vía inscripción (consolidación)
            Prefetch(
                'alumno__inscripciones',
                queryset=Inscripciones.objects.select_related(
                    'grupo__grado', 'grupo__seccion'
                ).filter(estado_inscripcion__in=['Activa', 'Graduado'])
            ),
        )
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
    EXPORT_ENCABEZADOS = INSCRIPCIONES_EXPORT_ENCABEZADOS

    # Subconjunto de columnas que se muestran en el PDF (datos principales).
    PDF_COLUMNAS = INSCRIPCIONES_PDF_COLUMNAS

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
            qs = qs.filter(
                alumno__primer_nombre__icontains=search
            ) | qs.filter(
                alumno__primer_apellido__icontains=search
            ) | qs.filter(
                alumno__cedula_escolar__icontains=search
            )

        # Optimización N+1: precarga de relaciones anidadas para serializadores
        # alumno_detalle necesita: alumno con direccion y profesor_encargado
        # (grado/sección del alumno se resuelven vía inscripción -> grupo)
        # grupo_academico_detalle necesita: grupo con periodo, grado, seccion, turno, profesor_director
        qs = qs.select_related(
            'alumno__id_direccion_residencia',
            'alumno__id_profesor_encargado',
            'grupo__periodo',
            'grupo__grado',
            'grupo__seccion',
            'grupo__turno',
            'grupo__profesor_director'
        ).prefetch_related(
            'alumno__representantes_vinculados__representante'
        )

        return qs



    @action(detail=False, methods=['get'], url_path='exportar-inscripciones-excel')
    def exportar_inscripciones_excel(self, request):
        """Encolar exportación asíncrona a Excel de inscripciones (responde 202)."""
        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay inscripciones que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            _respuesta_reporte_encolado('inscripciones', 'excel', qs),
            status=status.HTTP_202_ACCEPTED
        )

    @action(detail=False, methods=['get'], url_path='exportar-inscripciones-pdf')
    def exportar_inscripciones_pdf(self, request):
        """Encolar exportación asíncrona a PDF de inscripciones (responde 202)."""
        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay inscripciones que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            _respuesta_reporte_encolado('inscripciones', 'pdf', qs),
            status=status.HTTP_202_ACCEPTED
        )

    @action(detail=False, methods=['get'], url_path='exportar-inscripciones-csv')
    def exportar_inscripciones_csv(self, request):
        """Exportar a CSV las inscripciones filtradas (grado/seccion/estado/search)."""
        qs = self.get_queryset()

        if not qs.exists():
            return Response(
                {'error': 'No hay inscripciones que coincidan con los filtros especificados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        response = exportar_inscripciones_csv(qs)
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
        - select_related elimina las consultas N+1 al serializar.
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

        # --- Optimización N+1: carga directa de alumno y grupo con relaciones anidadas ---
        # El serializer necesita: alumno.*, grupo.*, grupo.id_grado.*, grupo.id_seccion.*
        qs = qs.select_related(
            'alumno',
            'grupo',
            'grupo__grado',
            'grupo__seccion',
            'profesor_registro'
        )

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

    response = exportar_asistencias_csv(queryset)
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

    response = exportar_asistencias_excel(queryset)
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

    response = exportar_asistencias_pdf(queryset, fecha_inicio, fecha_fin)
    return response

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
    response = generar_comprobante_inscripcion(inscripcion_id)

    if response is None:
        return Response({'error': 'Inscripción no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    return response


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
            'carnet_patria_codigo': openapi.Schema(type=openapi.TYPE_STRING),
            'carnet_patria_serial': openapi.Schema(type=openapi.TYPE_STRING),
            'numero_cuenta': openapi.Schema(type=openapi.TYPE_STRING),
            'tipo_cuenta': openapi.Schema(type=openapi.TYPE_STRING),
            'banco': openapi.Schema(type=openapi.TYPE_STRING),
            'entidad_federal_nacimiento': openapi.Schema(type=openapi.TYPE_STRING),
            'municipio_nacimiento': openapi.Schema(type=openapi.TYPE_STRING),
            'parroquia_nacimiento': openapi.Schema(type=openapi.TYPE_STRING),
            'apoyo_escolar': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            'vacunas_completas': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            'estado_civil_padres': openapi.Schema(type=openapi.TYPE_STRING),
            'tipo_vivienda': openapi.Schema(type=openapi.TYPE_STRING),
            'profesion_madre': openapi.Schema(type=openapi.TYPE_STRING),
            'profesion_padre': openapi.Schema(type=openapi.TYPE_STRING),
            'numero_hermanos': openapi.Schema(type=openapi.TYPE_INTEGER),
            'numero_en_el_planter': openapi.Schema(type=openapi.TYPE_INTEGER),
            'ingreso_familiar': openapi.Schema(type=openapi.TYPE_NUMBER),
            'observaciones': openapi.Schema(type=openapi.TYPE_STRING),
            'profesor_encargado': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Cédula o nombre completo del docente guía (se resuelve contra personal.Profesores)',
            ),
            'parentesco': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Parentesco del representante legal con el alumno',
            ),
            'representante': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description='Representante legal (requiere cedula, nombre y telefono para vincularlo)',
                properties={
                    'cedula': openapi.Schema(type=openapi.TYPE_STRING),
                    'nombre': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description='Nombre completo (se expande a primer_nombre/primer_apellido)',
                    ),
                    'telefono': openapi.Schema(type=openapi.TYPE_STRING),
                    'telefono_secundario': openapi.Schema(type=openapi.TYPE_STRING),
                    'email': openapi.Schema(type=openapi.TYPE_STRING),
                    'carnet_patria': openapi.Schema(type=openapi.TYPE_STRING),
                    'ocupacion': openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
            'direccion': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'calle': openapi.Schema(type=openapi.TYPE_STRING),
                    'ciudad': openapi.Schema(type=openapi.TYPE_STRING),
                    'estado': openapi.Schema(type=openapi.TYPE_STRING),
                    'referencia': openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
        },
        required=['primer_nombre', 'primer_apellido', 'numero_documento_identidad', 'cedula_escolar', 'fecha_nacimiento']
    ),
    responses={201: openapi.Response('Alumno creado exitosamente'), 400: openapi.Response('Error de validación')}
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@validate_webhook_signature
def webhook_google_forms(request):
    """
    Webhook para recibir datos de Google Forms/Google Apps Script.
    Crea automáticamente un alumno y opcionalmente su inscripción.
    Protected by validate_webhook_signature decorator.
    """
    try:
        data = request.data

        # Procesar creación de alumno
        alumno, error = procesar_alumno_webhook(data)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        # Procesar inscripción si se incluye id_grupo
        inscripcion = None
        if data.get('id_grupo'):
            inscripcion, error = procesar_inscripcion_webhook(alumno, data)
            if error:
                return Response(
                    {'error': error, 'alumno_id': alumno.id_alumno},
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


# ============================================================================
# ENDPOINTS DE CONSULTA/DESCARGA DE REPORTES ASÍNCRONOS (Misión 10)
# ============================================================================

@api_view(['GET'])
@permission_classes([EsProfesorOAdmin])
def estado_exportacion(request, reporte_id):
    """Estado de un reporte encolado: 'Procesando' | 'Completado' | 'Error'."""
    reporte = leer_estado_reporte(reporte_id)
    if reporte is None:
        return Response({'error': 'Reporte no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    return Response(reporte)


@api_view(['GET'])
@permission_classes([EsProfesorOAdmin])
def descargar_exportacion(request, reporte_id):
    """Descarga el archivo generado (solo si el reporte está 'Completado')."""
    reporte = leer_estado_reporte(reporte_id)
    if reporte is None:
        return Response({'error': 'Reporte no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    if reporte.get('estatus') == 'Error':
        return Response(
            {'error': 'El reporte falló al generarse', 'detalle': reporte.get('detalle')},
            status=status.HTTP_409_CONFLICT
        )
    ruta = ruta_archivo_reporte(reporte_id, reporte)
    if ruta is None:
        return Response(
            {'error': 'El reporte aún se está procesando'},
            status=status.HTTP_409_CONFLICT
        )
    return FileResponse(
        open(ruta, 'rb'),
        as_attachment=True,
        filename=reporte.get('archivo', 'reporte.bin')
    )


# ============================================================================
# ENDPOINT DE INSCRIPCIÓN CON REPRESENTANTE ANIDADO
# ============================================================================

class AlumnoInscripcionAPIView(APIView):
    """
    Endpoint para inscribir un alumno junto con su representante legal
    en una sola operación atómica.
    Requiere autenticación JWT válida (IsAuthenticated).
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AlumnoInscripcionSerializer

    @swagger_auto_schema(
        tags=['Inscripciones'],
        operation_summary='Inscribir alumno con representante anidado',
        operation_description='Crea alumno, representante (idempotente por cédula), '
                              'vínculo AlumnoRepresentante e Inscripción en una transacción.',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['primer_nombre', 'primer_apellido', 'tipo_documento_identidad',
                      'numero_documento_identidad', 'fecha_nacimiento', 'genero',
                      'representante', 'id_grupo'],
            properties={
                'primer_nombre': openapi.Schema(type=openapi.TYPE_STRING),
                'primer_apellido': openapi.Schema(type=openapi.TYPE_STRING),
                'tipo_documento_identidad': openapi.Schema(type=openapi.TYPE_STRING),
                'numero_documento_identidad': openapi.Schema(type=openapi.TYPE_STRING),
                'cedula_escolar': openapi.Schema(type=openapi.TYPE_STRING),
                'fecha_nacimiento': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                'genero': openapi.Schema(type=openapi.TYPE_STRING),
                'representante': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    required=['cedula', 'nombre', 'apellido', 'telefono'],
                    properties={
                        'cedula': openapi.Schema(type=openapi.TYPE_STRING),
                        'nombre': openapi.Schema(type=openapi.TYPE_STRING),
                        'apellido': openapi.Schema(type=openapi.TYPE_STRING),
                        'telefono': openapi.Schema(type=openapi.TYPE_STRING),
                        'correo': openapi.Schema(type=openapi.TYPE_STRING, format='email'),
                    },
                ),
                'id_grupo': openapi.Schema(type=openapi.TYPE_INTEGER),
                'fecha_inscripcion': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                'monto_pago': openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        responses={
            201: openapi.Response('Inscripción creada exitosamente'),
            400: openapi.Response('Error de validación'),
            401: openapi.Response('No autenticado'),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = AlumnoInscripcionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inscripcion = serializer.save()
        return Response(
            {
                'success': True,
                'message': 'Inscripción creada exitosamente',
                'inscripcion_id': inscripcion.id_inscripcion,
                'alumno_id': inscripcion.alumno.id_alumno,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================================
# ENDPOINTS DE CONTROL DINÁMICO DE INSCRIPCIONES EXTERNAS
# ============================================================================

class InscripcionDocenteExternaAPIView(APIView):
    """
    Endpoint público para inscripción externa de alumnos.

    Accesible por URL externa sin sesión JWT (AllowAny).
    Valida un token de acceso seguro y el estado del periodo de inscripción
    antes de crear el alumno y su inscripción.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = AlumnoInscripcionSerializer

    def post(self, request, *args, **kwargs):
        # 1) Extraer el token de los parámetros de la URL
        token = request.query_params.get('token')
        if not token:
            return Response(
                {'success': False, 'error': 'Token de acceso requerido.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2) Buscar el PeriodoInscripcion por el token (genérico para no filtrar info)
        try:
            periodo = PeriodoInscripcion.objects.get(token_acceso=token)
        except PeriodoInscripcion.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Acceso denegado.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception:
            logger.debug('Error buscando PeriodoInscripcion por token', exc_info=True)
            return Response(
                {'success': False, 'error': 'Acceso denegado.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 3) Regla de negocio: verificar disponibilidad del periodo
        if not periodo.esta_disponible():
            return Response(
                {
                    'success': False,
                    'error': 'El periodo de inscripciones ha concluido o está deshabilitado.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4) Procesar la inscripción con el serializador existente
        serializer = AlumnoInscripcionSerializer(data=request.data)
        if serializer.is_valid():
            try:
                inscripcion = serializer.save()
                return Response(
                    {
                        'success': True,
                        'message': 'Inscripción creada exitosamente.',
                        'inscripcion_id': inscripcion.id_inscripcion,
                        'alumno_id': inscripcion.alumno.id_alumno,
                    },
                    status=status.HTTP_201_CREATED,
                )
            except Exception:
                logger.debug('Error creando inscripción externa', exc_info=True)
                return Response(
                    {'success': False, 'error': 'Error interno al procesar la inscripción.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(
            {'success': False, 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class AlternarUrlInscripcionAPIView(APIView):
    """
    Endpoint para alternar el estado del switch de inscripción (activo_manual).

    Requiere autenticación JWT (IsAuthenticated) de un administrador legítimo.
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk, *args, **kwargs):
        try:
            periodo = PeriodoInscripcion.objects.get(pk=pk)
        except PeriodoInscripcion.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Periodo de inscripción no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.debug('Error buscando PeriodoInscripcion por pk', exc_info=True)
            return Response(
                {'success': False, 'error': 'Error interno al buscar el periodo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activo_manual = request.data.get('activo_manual')
        if activo_manual is None:
            return Response(
                {'success': False, 'error': 'El campo activo_manual es requerido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        periodo.activo_manual = bool(activo_manual)
        periodo.save()

        return Response(
            {
                'success': True,
                'message': f'Estado de inscripción actualizado: {"activo" if periodo.activo_manual else "inactivo"}.',
                'activo_manual': periodo.activo_manual,
                'token_acceso': periodo.token_acceso,
            },
            status=status.HTTP_200_OK,
        )

