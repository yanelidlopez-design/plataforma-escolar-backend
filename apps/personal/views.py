from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import FileResponse, HttpResponse
import csv

from .models import Profesores, RepresentantesLegales, AlumnoRepresentante
from .reports_personal import (
    generar_excel_alumnos_representantes,
    generar_excel_personal,
    generar_pdf_alumnos_representantes,
    generar_pdf_personal,
)
from .serializers import ProfesoresSerializer, RepresentantesLegalesSerializer, AlumnoRepresentanteSerializer
from .services import PersonalService
from apps.core.serializers import RestablecerContrasenaSerializer
from apps.academico.permissions import EsAdministrador


@swagger_auto_schema(tags=['Personal'])
class PersonalViewSet(viewsets.ModelViewSet):
    queryset = Profesores.objects.select_related('id_usuario').prefetch_related('hijos')
    serializer_class = ProfesoresSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['cedula', 'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido', 'cargo']

    def get_queryset(self):
        """
        Filtrado manual por query params (django-filter NO está disponible):
        GET /api/personal/personal/?cargo=Profesor
        Cargos inválidos se ignoran limpiamente (fail-soft en lectura);
        la validación estricta de cargos ocurre en el POST (serializer).
        """
        qs = super().get_queryset()
        cargo = (self.request.query_params.get('cargo') or '').strip()
        if cargo:
            validos = {codigo for codigo, _ in Profesores.CARGO_CHOICES}
            if cargo in validos:
                qs = qs.filter(cargo=cargo)
        return qs

    def perform_create(self, serializer):
        """
        La tabla legacy `profesores` exige id_usuario (NOT NULL, UNIQUE, FK a usuarios).
        Si el payload no trae id_usuario, se crea automáticamente el Usuario vinculado
        (con rol derivado de la categoría) de forma atómica para no dejar registros huérfanos.

        Toda la lógica de dominio (rol por categoría, email/nombre de usuario
        únicos y la transacción Usuario + Profesor) vive en PersonalService.
        Se asigna la instancia creada a ``serializer.instance`` para que la
        respuesta 201 serialice el mismo payload que antes de la refactor
        (equivale a lo que hacía ``serializer.save()``).
        """
        serializer.instance = PersonalService.crear_personal_con_usuario(
            serializer.validated_data,
            self.request.data.get('email') or self.request.data.get('correo'),
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='restablecer-password',
        permission_classes=[EsAdministrador],
    )
    def restablecer_password(self, request, pk=None):
        persona = self.get_object()
        if not persona.id_usuario:
            return Response(
                {'detail': 'Este registro de personal no tiene una cuenta de usuario vinculada.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = RestablecerContrasenaSerializer(
            data=request.data,
            context={'user': persona.id_usuario},
        )
        serializer.is_valid(raise_exception=True)
        persona.id_usuario.set_password(serializer.validated_data['contrasena_nueva'])
        persona.id_usuario.save(update_fields=['clave_hash'])
        return Response({'detail': 'Contraseña restablecida correctamente.'})

    @swagger_auto_schema(
        method='GET',
        operation_description='Exportar personal filtrado por cargo en formato Excel (.xlsx)',
        manual_parameters=[
            openapi.Parameter('cargo', openapi.IN_QUERY, description='Cargo del personal (opcional)', type=openapi.TYPE_STRING),
        ],
        responses={200: openapi.Response('Archivo Excel')}
    )
    @action(detail=False, methods=['get'], url_path='exportar-excel')
    def exportar_excel(self, request):
        """Listado en Excel; la maquetación vive en reports_personal (-> BytesIO)."""
        queryset = self.filter_queryset(self.get_queryset()).prefetch_related('hijos')
        buffer = generar_excel_personal(queryset)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename='listado_personal.xlsx',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    @swagger_auto_schema(
        method='GET',
        operation_description='Exportar personal filtrado por cargo en formato PDF',
        manual_parameters=[
            openapi.Parameter('cargo', openapi.IN_QUERY, description='Cargo del personal (opcional)', type=openapi.TYPE_STRING),
        ],
        responses={200: openapi.Response('Archivo PDF')}
    )
    @action(detail=False, methods=['get'], url_path='exportar-pdf')
    def exportar_pdf(self, request):
        """Listado en PDF; la maquetación vive en reports_personal (-> BytesIO)."""
        buffer = generar_pdf_personal(
            self.filter_queryset(self.get_queryset()),
            cargo=(request.query_params.get('cargo') or '').strip(),
        )
        return FileResponse(
            buffer,
            as_attachment=True,
            filename='listado_personal.pdf',
            content_type='application/pdf',
        )

    @action(detail=False, methods=['get'], url_path='exportar-csv')
    def exportar_csv(self, request):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="listado_personal.csv"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow([
            'Cédula', 'Primer Nombre', 'Segundo Nombre', 'Primer Apellido',
            'Segundo Apellido', 'Cargo', 'Categoría', 'Teléfono', 'Correo',
        ])

        for p in self.filter_queryset(self.get_queryset()):
            correo = p.correo or (getattr(p.id_usuario, 'email', '') if p.id_usuario else '') or ''
            writer.writerow([
                p.cedula,
                p.primer_nombre,
                p.segundo_nombre or '',
                p.primer_apellido,
                p.segundo_apellido or '',
                p.cargo,
                p.categoria or '',
                p.telefono or '',
                correo,
            ])

        return response


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

    writer = csv.writer(response)
    writer.writerow(['Alumno', 'Representante', 'Teléfono', 'Parentesco', 'Es Principal'])

    relaciones = AlumnoRepresentante.objects.select_related('alumno', 'representante')
    for relacion in relaciones:
        writer.writerow([
            f"{relacion.alumno.primer_nombre} {relacion.alumno.primer_apellido}",
            f"{relacion.representante.primer_nombre} {relacion.representante.primer_apellido}",
            relacion.representante.telefono_principal or 'No registrado',
            relacion.parentesco or 'No especificado',
            "Sí" if relacion.es_principal else "No"
        ])

    return response


@swagger_auto_schema(
    method='GET',
    operation_description='Exportar alumnos y representantes en formato Excel (.xlsx)',
    tags=['Exportaciones'],
    responses={200: openapi.Response('Archivo Excel')}
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def exportar_alumnos_representantes_excel(request):
    buffer = generar_excel_alumnos_representantes(
        AlumnoRepresentante.objects.select_related('alumno', 'representante')
    )
    return FileResponse(
        buffer,
        as_attachment=True,
        filename='alumnos_y_representantes.xlsx',
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@swagger_auto_schema(
    method='GET',
    operation_description='Exportar alumnos y representantes en formato PDF',
    tags=['Exportaciones'],
    responses={200: openapi.Response('Archivo PDF')}
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def exportar_alumnos_representantes_pdf(request):
    buffer = generar_pdf_alumnos_representantes(
        AlumnoRepresentante.objects.select_related('alumno', 'representante')
    )
    return FileResponse(
        buffer,
        as_attachment=True,
        filename='alumnos_y_representantes.pdf',
        content_type='application/pdf',
    )


@swagger_auto_schema(tags=['Representantes Legales'])
class RepresentantesLegales(viewsets.ModelViewSet):
    queryset = RepresentantesLegales.objects.select_related('id_direccion_residencia').all()
    serializer_class = RepresentantesLegalesSerializer
    search_fields = ['cedula', 'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido']


@swagger_auto_schema(tags=['Alumno-Representante'])
class AlumnoRepresentanteViewSet(viewsets.ModelViewSet):
    queryset = AlumnoRepresentante.objects.all()
    serializer_class = AlumnoRepresentanteSerializer
    filterset_fields = ['id_alumno', 'id_representante', 'es_principal']
