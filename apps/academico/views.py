from rest_framework import viewsets, filters, status, permissions, exceptions
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import HttpResponse, FileResponse
from django.shortcuts import render
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError, Prefetch
import logging
import re
from .models import Alumnos, GruposAcademicos, Inscripciones, Calificaciones, Asistencias, PeriodoInscripcion, PeriodoCalificacion
from .serializers import (
    AlumnosSerializer, GruposAcademicosSerializer,
    InscripcionesSerializer, CalificacionesSerializer, AsistenciasSerializer,
    AlumnoInscripcionSerializer,
    PeriodoInscripcionSerializer,
    PeriodoCalificacionSerializer,
    CargaMasivaCalificacionesSerializer,
    CargaMasivaCriteriosSerializer,
    ConstanciaProsecucionFinalSerializer,
)
from .permissions import EsProfesorOAdmin, EsAdministrador
from .decorators import validate_webhook_signature
from .reports import (
    exportar_alumnos_excel, exportar_alumnos_pdf, exportar_alumnos_csv,
    exportar_inscripciones_excel, exportar_inscripciones_pdf, exportar_inscripciones_csv,
    exportar_asistencias_excel, exportar_asistencias_pdf, exportar_asistencias_csv,
    ALUMNOS_EXPORT_ENCABEZADOS, ALUMNOS_PDF_COLUMNAS,
    INSCRIPCIONES_EXPORT_ENCABEZADOS, INSCRIPCIONES_PDF_COLUMNAS,
    _crear_estilos_comprobante, _separar_documento, _texto_seguro, _tabla_clave_valor,
    generar_pdf_informe_descriptivo,
)
from .services.inscripcion_service import generar_comprobante_inscripcion
from .services.webhook_service import procesar_alumno_webhook, procesar_inscripcion_webhook
from .tasks import encolar_exportacion, leer_estado_reporte, ruta_archivo_reporte
from apps.core.models import ConfiguracionPlantel, GradosAcademicos, Secciones
from apps.core.serializers import GradosAcademicosSerializer, SeccionesSerializer
from apps.personal.models import Profesores

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

    - GET  /api/academico/inscripcion-externa/?token=...  → formulario HTML
      móvil para que el representante se inscriba sin usuario en la plataforma.
    - POST /api/academico/inscripcion-externa/?token=...  → crea la inscripción.

    Accesible por URL externa sin sesión JWT (AllowAny).
    Valida un token de acceso seguro y el estado del periodo de inscripción
    antes de crear el alumno y su inscripción.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = AlumnoInscripcionSerializer

    def _validar_periodo(self, request):
        """
        Compartido por GET y POST: extrae el token de la URL, busca el periodo
        y valida que esté disponible. Devuelve (periodo, Response_de_error).
        """
        token = request.query_params.get('token')
        if not token:
            return None, Response(
                {'success': False, 'error': 'Token de acceso requerido.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            periodo = PeriodoInscripcion.objects.get(token_acceso=token)
        except PeriodoInscripcion.DoesNotExist:
            return None, Response(
                {'success': False, 'error': 'Acceso denegado.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception:
            logger.debug('Error buscando PeriodoInscripcion por token', exc_info=True)
            return None, Response(
                {'success': False, 'error': 'Acceso denegado.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not periodo.esta_disponible():
            return None, Response(
                {'success': False, 'error': 'El periodo de inscripciones ha concluido o está deshabilitado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return periodo, None

    def get(self, request, *args, **kwargs):
        """
        Renderiza el formulario público de inscripción (HTML móvil).

        Si el token es inválido o el periodo no está disponible, devuelve un
        JSON de error con el código correspondiente (403/400).
        """
        periodo, error = self._validar_periodo(request)
        if error is not None:
            return error

        # Grupos disponibles para el selector, con etiqueta legible.
        grupos = (
            GruposAcademicos.objects
            .select_related('grado', 'seccion', 'turno', 'nivel')
            .order_by('nivel__nombre_nivel', 'grado__orden', 'seccion__nombre_seccion')
        )
        grupos_data = [
            {
                'id': g.id_grupo,
                'etiqueta': (
                    f"{g.grado.nombre_grado} '{g.seccion.nombre_seccion}'"
                    f" — {g.turno.nombre_turno}"
                    + (f" ({g.nivel.nombre_nivel})" if g.nivel else '')
                ),
            }
            for g in grupos
        ]

        # Personal del plantel para el selector de "Profesor Encargado".
        # Se consulta en cada GET: el combo se actualiza solo cuando se
        # agregan más profesores en la plataforma (no es estático).
        profesores_data = [
            {
                'id': p.id_profesor,
                'nombre': f"{p.primer_nombre} {p.primer_apellido}".strip(),
            }
            for p in Profesores.objects.order_by('primer_nombre', 'primer_apellido')
        ]

        return render(
            request,
            'inscripcion_externa.html',
            {
                'periodo': periodo,
                'grupos': grupos_data,
                'profesores': profesores_data,
                'token': request.query_params.get('token'),
            },
        )

    def post(self, request, *args, **kwargs):
        # 1) Extraer el token de la URL y validar el periodo (helper compartido).
        periodo, error = self._validar_periodo(request)
        if error is not None:
            return error

        # 2) Procesar la inscripción con el serializador existente.
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


# ============================================================================
# ENDPOINTS DE PERIODOS DE INSCRIPCION (ADMIN): LISTADO, CREACIÓN Y EDICIÓN
# ============================================================================

class PeriodoInscripcionListCreateAPIView(ListCreateAPIView):
    """
    Listado y creación de periodos de inscripción para el panel administrativo.

    - GET  /api/academico/periodos/          → lista todos los periodos.
    - POST /api/academico/periodos/          → crea un periodo nuevo (el
      token_acceso se autogenera en el modelo).

    Devuelve pk, nombre, fechas, estado del switch (activo_manual) y
    token_acceso. Requiere autenticación JWT (IsAuthenticated).
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PeriodoInscripcionSerializer
    queryset = PeriodoInscripcion.objects.all()

    @swagger_auto_schema(
        tags=['Periodos de Inscripción'],
        operation_summary='Listar periodos de inscripción',
        operation_description='Retorna todos los periodos de inscripción con su pk, '
                              'nombre, calendario, activo_manual y token_acceso. '
                              'Requiere autenticación JWT.',
        responses={
            200: PeriodoInscripcionSerializer(many=True),
            401: openapi.Response('No autenticado'),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Periodos de Inscripción'],
        operation_summary='Crear periodo de inscripción',
        operation_description='Crea un periodo nuevo con nombre y calendario. '
                              'El token_acceso de la URL pública se autogenera. '
                              'Requiere autenticación JWT.',
        request_body=PeriodoInscripcionSerializer,
        responses={
            201: PeriodoInscripcionSerializer,
            400: openapi.Response('Error de validación'),
            401: openapi.Response('No autenticado'),
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class PeriodoInscripcionDetailAPIView(RetrieveUpdateDestroyAPIView):
    """
    Detalle, edición y eliminación de un periodo de inscripción para el panel administrativo.

    - GET    /api/academico/periodos/<id>/          → detalle del periodo.
    - PATCH  /api/academico/periodos/<id>/          → edición parcial (nombre,
      fecha_inicio, fecha_fin) desde el formulario del frontend.
    - DELETE /api/academico/periodos/<id>/          → elimina el periodo.

    Requiere autenticación JWT (IsAuthenticated).
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PeriodoInscripcionSerializer
    queryset = PeriodoInscripcion.objects.all()

    @swagger_auto_schema(
        tags=['Periodos de Inscripción'],
        operation_summary='Detalle de un periodo de inscripción',
        operation_description='Retorna el periodo con su pk, nombre, calendario, '
                              'activo_manual y token_acceso. Requiere autenticación JWT.',
        responses={
            200: PeriodoInscripcionSerializer,
            401: openapi.Response('No autenticado'),
            404: openapi.Response('Periodo no encontrado'),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Periodos de Inscripción'],
        operation_summary='Editar periodo de inscripción',
        operation_description='Actualización parcial (PATCH) del nombre y las fechas '
                              'del periodo. Valida que fecha_fin > fecha_inicio. '
                              'Requiere autenticación JWT.',
        request_body=PeriodoInscripcionSerializer,
        responses={
            200: PeriodoInscripcionSerializer,
            400: openapi.Response('Error de validación'),
            401: openapi.Response('No autenticado'),
            404: openapi.Response('Periodo no encontrado'),
        },
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Periodos de Inscripción'],
        operation_summary='Eliminar periodo de inscripción',
        operation_description='Elimina permanentemente un periodo de inscripción. '
                              'Si el periodo estaba activo, el enlace público deja '
                              'de funcionar. Requiere autenticación JWT.',
        responses={
            204: openapi.Response('Periodo eliminado'),
            401: openapi.Response('No autenticado'),
            404: openapi.Response('Periodo no encontrado'),
        },
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class CargaCalificacionesDocenteExternaAPIView(APIView):
    """
    Endpoint público para la carga masiva de calificaciones por los docentes.

    - POST /api/academico/calificaciones/cargar-externa/?token=...

    Accesible por URL externa sin sesión JWT (AllowAny). Valida el token del
    lapso y que el periodo esté abierto (esta_abierto(): switch manual +
    fecha límite) antes de persistir la sección completa con guardar_lote(),
    que garantiza atomicidad (rollback total) e idempotencia (update_or_create).
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = CargaMasivaCalificacionesSerializer

    @swagger_auto_schema(
        tags=['Calificaciones'],
        operation_summary='Carga masiva de notas de un lapso (docente externo)',
        operation_description='Recibe el lote de calificaciones de una sección '
                              'para un lapso abierto y lo persiste de forma '
                              'atómica e idempotente. Acceso por token en la '
                              'URL sin sesión JWT.',
        manual_parameters=[
            openapi.Parameter(
                'token', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                description='Token seguro del periodo de calificación.',
            ),
        ],
        request_body=CargaMasivaCalificacionesSerializer,
        responses={
            200: openapi.Response('Lote guardado (desglose creadas/actualizadas)'),
            400: openapi.Response('Periodo cerrado, datos inválidos o reglas pedagógicas'),
            403: openapi.Response('Token ausente o inválido'),
        },
    )
    def post(self, request, *args, **kwargs):
        # 1) Token de acceso en los query params de la URL.
        token = request.query_params.get('token')
        if not token:
            return Response(
                {'success': False, 'error': 'Token de acceso requerido.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2) Periodo de calificación correspondiente al token.
        try:
            periodo = PeriodoCalificacion.objects.get(token_acceso=token)
        except PeriodoCalificacion.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Acceso denegado.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception:
            logger.debug('Error buscando PeriodoCalificacion por token', exc_info=True)
            return Response(
                {'success': False, 'error': 'Acceso denegado.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 3) Regla estricta: el lapso debe estar abierto (switch manual y
        #    fecha límite de carga de notas).
        if not periodo.esta_abierto():
            return Response(
                {'success': False,
                 'error': 'El periodo de carga de notas ha concluido o está cerrado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4) Validación sintáctica del lote.
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'error': 'Datos inválidos.', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5) Persistencia atómica e idempotente de la sección completa.
        try:
            resumen = serializer.guardar_lote(periodo_objeto=periodo)
        except ValidationError as exc:
            # El rollback total y la auditoría (logger.debug) ya ocurrieron
            # dentro de guardar_lote(); aquí se traduce a respuesta 400.
            detalle = exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            return Response(
                {'success': False,
                 'error': 'Una o más notas incumplen las reglas de calificación; no se guardó ninguna.',
                 'details': detalle},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            logger.debug('Error de integridad guardando lote de calificaciones', exc_info=True)
            return Response(
                {'success': False, 'error': 'El lote referencia alumnos o grupos inexistentes.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.debug('Error inesperado guardando lote de calificaciones', exc_info=True)
            return Response(
                {'success': False, 'error': 'No se pudieron guardar las calificaciones.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({'success': True, **resumen}, status=status.HTTP_200_OK)


class CargaCriteriosDocenteExternaAPIView(APIView):
    """
    Endpoint público para la carga masiva de criterios cualitativos por los
    docentes (sección completa de alumnos).

    - POST /api/academico/calificaciones/cargar-criterios-externa/?token=...

    Accesible por URL externa sin sesión JWT (AllowAny). Valida el token del
    lapso y que el periodo esté abierto (esta_abierto(): switch manual +
    fecha límite) antes de persistir con guardar_lote_criterios(), que
    garantiza atomicidad (rollback total) e idempotencia (update_or_create).
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = CargaMasivaCriteriosSerializer

    @swagger_auto_schema(
        tags=['Calificaciones'],
        operation_summary='Carga masiva de criterios cualitativos por sección (docente externo)',
        operation_description='Recibe el lote de evaluaciones de criterios '
                              'cualitativos de una sección para un lapso '
                              'abierto y lo persiste de forma atómica e '
                              'idempotente. Acceso por token en la URL sin '
                              'sesión JWT.',
        manual_parameters=[
            openapi.Parameter(
                'token', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                description='Token seguro del periodo de calificación.',
            ),
        ],
        request_body=CargaMasivaCriteriosSerializer,
        responses={
            200: openapi.Response('Lote guardado (desglose creadas/actualizadas)'),
            400: openapi.Response('Periodo cerrado, datos inválidos o reglas de negocio'),
            403: openapi.Response('Token ausente o inválido'),
        },
    )
    def post(self, request, *args, **kwargs):
        # 1) Token de acceso en los query params de la URL.
        token = request.query_params.get('token')
        if not token:
            return Response(
                {'success': False, 'error': 'Token de acceso requerido.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2) Periodo de calificación correspondiente al token.
        try:
            periodo = PeriodoCalificacion.objects.get(token_acceso=token)
        except PeriodoCalificacion.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Acceso denegado.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception:
            logger.debug('Error buscando PeriodoCalificacion por token (criterios)', exc_info=True)
            return Response(
                {'success': False, 'error': 'Acceso denegado.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 3) Regla estricta: el lapso debe estar abierto (switch manual y
        #    fecha límite de carga de notas).
        if not periodo.esta_abierto():
            return Response(
                {'success': False,
                 'error': 'El periodo de carga de notas ha concluido o está cerrado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4) Validación sintáctica del lote de criterios.
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'error': 'Datos inválidos.', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5) Persistencia atómica e idempotente del lote de criterios.
        try:
            resumen = serializer.guardar_lote_criterios(periodo_objeto=periodo)
        except ValidationError as exc:
            # El rollback total y la auditoría (logger.debug) ya ocurrieron
            # dentro de guardar_lote_criterios(); aquí se traduce a respuesta 400.
            detalle = exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            return Response(
                {'success': False,
                 'error': 'Una o más evaluaciones incumplen las reglas de calificación; no se guardó ninguna.',
                 'details': detalle},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            logger.debug('Error de integridad guardando lote de criterios', exc_info=True)
            return Response(
                {'success': False, 'error': 'El lote referencia alumnos, criterios o grupos inexistentes.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.debug('Error inesperado guardando lote de criterios', exc_info=True)
            return Response(
                {'success': False, 'error': 'No se pudieron guardar las evaluaciones de criterios.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({'success': True, **resumen}, status=status.HTTP_200_OK)


class ConfiguracionPeriodoCalificacionViewSet(viewsets.ModelViewSet):
    """
    Control administrativo de los periodos (lapsos) de calificación.

    Requiere autenticación JWT (IsAuthenticated). Permite al personal
    administrativo del panel escolar:
    - Consultar los lapsos existentes (Diciembre, Abril, Julio).
    - Modificar la fecha límite de carga de notas.
    - Alternar el switch manual 'activo_manual' de apertura/cierre.

    Rutas (registradas en el DefaultRouter de academico):
    - GET/POST  /api/academico/periodos-calificacion/
    - GET/PUT/PATCH/DELETE /api/academico/periodos-calificacion/{pk}/
    """
    queryset = PeriodoCalificacion.objects.all().order_by('numero_periodo')
    serializer_class = PeriodoCalificacionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_destroy(self, instance):
        """
        CalificacionLiteral referencia al periodo con PROTECT: eliminarlo con
        notas registradas se traduce en un 400 auditado (no en un 500 crudo).
        """
        try:
            instance.delete()
        except ProtectedError:
            logger.debug(
                'Intento de eliminar PeriodoCalificacion %s con calificaciones asociadas',
                instance.pk, exc_info=True,
            )
            raise exceptions.ValidationError(
                'No se puede eliminar el periodo porque tiene calificaciones registradas.'
            )



class DescargaInformeDescriptivoAPIView(APIView):
    """
    Endpoint administrativo para descargar el Informe Descriptivo Trimestral
    de un alumno en un lapso de calificación determinado.

    - GET /api/academico/calificaciones/informe-lapso-pdf/<int:alumno_id>/<int:periodo_id>/

    Requiere autenticación JWT (IsAuthenticated): uso exclusivo del personal
    administrativo de la plataforma escolar.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        id_alumno = kwargs.get('alumno_id') or request.query_params.get('id_alumno')
        id_periodo = kwargs.get('periodo_id') or request.query_params.get('id_periodo')

        if not id_alumno or not id_periodo:
            return Response(
                {'success': False, 'error': 'Se requieren id_alumno e id_periodo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            alumno = Alumnos.objects.get(pk=id_alumno)
        except Alumnos.DoesNotExist:
            logger.debug('Alumno no encontrado: id=%s', id_alumno, exc_info=True)
            return Response(
                {'success': False, 'error': 'Alumno no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.debug('Error buscando alumno id=%s', id_alumno, exc_info=True)
            return Response(
                {'success': False, 'error': 'Error al buscar el alumno.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            periodo = PeriodoCalificacion.objects.get(pk=id_periodo)
        except PeriodoCalificacion.DoesNotExist:
            logger.debug('Periodo no encontrado: id=%s', id_periodo, exc_info=True)
            return Response(
                {'success': False, 'error': 'Periodo de calificación no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.debug('Error buscando periodo id=%s', id_periodo, exc_info=True)
            return Response(
                {'success': False, 'error': 'Error al buscar el periodo.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Obtener el grupo del alumno a través de sus evaluaciones en el lapso.
        grupo = None
        try:
            ev = EvaluacionLapsoCriterio.objects.filter(
                alumno=alumno, periodo=periodo
            ).select_related('criterio__grupo').first()
            if ev:
                grupo = ev.criterio.grupo
        except Exception:
            logger.debug(
                'Error obteniendo grupo del alumno %s en periodo %s',
                id_alumno, id_periodo, exc_info=True,
            )

        try:
            pdf_buffer = generar_pdf_informe_descriptivo(alumno, periodo, grupo)
        except Exception:
            logger.debug(
                'Error generando PDF informe descriptivo alumno=%s periodo=%s',
                id_alumno, id_periodo, exc_info=True,
            )
            return Response(
                {'success': False, 'error': 'No se pudo generar el informe PDF.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        cedula = (
            alumno.cedula_escolar or alumno.numero_documento_identidad or id_alumno
        )
        lapso = periodo.numero_periodo
        filename = f"Informe_Descriptivo_{cedula}_Lapso{lapso}.pdf"

        response = FileResponse(
            pdf_buffer,
            content_type='application/pdf',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# ============================================================================
# SERVICIO B: CONSTANCIA DE PROSECUCIÓN FINAL (VEREDICTO ANUAL DE JULIO)
# ============================================================================

class RegistrarConstanciaProsecucionAPIView(APIView):
    """
    Registro administrativo de la Constancia de Prosecución Final.

    Guarda en MariaDB el veredicto definitivo anual del alumno emitido en
    Julio (literal final A-E y grado de promoción). Uso exclusivo del
    personal administrativo y de la Dirección de la escuela desde la
    plataforma escolar: requiere autenticación JWT (IsAuthenticated).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ConstanciaProsecucionFinalSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'success': True,
                    'message': 'Constancia de prosecución final registrada correctamente.',
                    'constancia': serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {'success': False, 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

