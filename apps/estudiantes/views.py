"""
Vistas API REST de Django REST Framework (DRF)
Plataforma Escolar Backend
"""

from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction

from .models import (
    Alumno, RepresentanteLegal, Direccion, Inscripcion, Calificacion, GrupoAcademico
)
from .serializers import (
    AlumnoDetalleSerializer, AlumnoRegistroCompletoSerializer,
    RepresentanteLegalSerializer, DireccionSerializer,
    InscripcionSerializer, CalificacionSerializer
)


class AlumnoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para la gestión de alumnos y sus expedientes completos.
    Soporta filtros por género, estatus, cédula, búsqueda por nombre y ordenamiento.
    """
    queryset = Alumno.objects.all().select_related('id_direccion_residencia').order_by('primer_apellido', 'primer_nombre')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'genero', 'estatus_general', 'tipo_documento_identidad',
        'apoyo_escolar', 'vacunas_completas', 'discapacidad'
    ]
    search_fields = [
        'numero_documento_identidad', 'cedula_escolar',
        'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido'
    ]
    ordering_fields = ['primer_apellido', 'fecha_nacimiento', 'fecha_inscripcion_inicial']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AlumnoRegistroCompletoSerializer
        return AlumnoDetalleSerializer

    @action(detail=True, methods=['get'])
    def historial_inscripciones(self, request, pk=None):
        alumno = self.get_object()
        inscripciones = Inscripcion.objects.filter(id_alumno=alumno).select_related('id_grupo')
        serializer = InscripcionSerializer(inscripciones, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def resumen_antropometrico(self, request):
        alumnos = self.get_queryset()
        total = alumnos.count()
        sin_vacunas = alumnos.filter(vacunas_completas=False).count()
        con_discapacidad = alumnos.filter(discapacidad=True).count()
        con_apoyo = alumnos.filter(apoyo_escolar=True).count()

        return Response({
            'total_estudiantes': total,
            'sin_vacunas_completas': sin_vacunas,
            'con_discapacidad': con_discapacidad,
            'con_apoyo_escolar': con_apoyo
        })


class RepresentanteLegalViewSet(viewsets.ModelViewSet):
    """
    ViewSet para la administración de representantes legales.
    """
    queryset = RepresentanteLegal.objects.all().select_related('id_direccion_residencia').order_by('apellidos', 'nombres')
    serializer_class = RepresentanteLegalSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['ocupacion']
    search_fields = ['cedula', 'nombres', 'apellidos', 'telefono', 'email']


class DireccionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para la gestión de direcciones de residencia.
    """
    queryset = Direccion.objects.all()
    serializer_class = DireccionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['ciudad', 'estado', 'calle']


class InscripcionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para inscripciones de alumnos en grupos académicos.
    """
    queryset = Inscripcion.objects.all().select_related('id_alumno', 'id_grupo')
    serializer_class = InscripcionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['estado_inscripcion', 'id_grupo', 'id_alumno']


class CalificacionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para el registro de calificaciones.
    """
    queryset = Calificacion.objects.all().select_related('id_inscripcion', 'id_profesor')
    serializer_class = CalificacionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['calificacion', 'id_inscripcion', 'id_profesor']
