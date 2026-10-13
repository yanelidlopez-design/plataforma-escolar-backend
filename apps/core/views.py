from rest_framework import viewsets, permissions, status
from rest_framework.decorators import permission_classes
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from drf_yasg.utils import swagger_auto_schema
from django.conf import settings
from .models import (
    Direcciones, ConfiguracionPlantel, PeriodosAcademicos,
    NivelesEducativos, Turnos, GradosAcademicos, Secciones, Usuarios
)
from .serializers import (
    DireccionesSerializer, ConfiguracionPlantelSerializer, PeriodosAcademicosSerializer,
    NivelesEducativosSerializer, TurnosSerializer, GradosAcademicosSerializer,
    SeccionesSerializer, UsuariosSerializer
)

# Permisos globales para los conjuntos de vistas de control del plantel
from apps.academico.permissions import EsAdministrador

@swagger_auto_schema(method='post', tags=['Authentication'])
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def custom_token_obtain(request):
    """Custom token endpoint for Usuarios model with nombre_usuario field"""
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response(
            {'detail': 'Username and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = Usuarios.objects.get(nombre_usuario=username)
        if user.check_password(password) and user.activo:
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            # Set access_token as HttpOnly cookie
            response = Response({
                # 'access' también en el body: en dev el frontend corre en otro
                # origen (p. ej. :5173) y las cookies SameSite=Lax no viajan en
                # XHR cross-origin, así que el cliente usa Authorization: Bearer.
                'access': access_token,
                'refresh': refresh_token,
                'user': {
                    'username': user.nombre_usuario,
                    'id_usuario': user.id_usuario,
                    'activo': user.activo
                }
            })

            # Use secure=True in production, secure=False in development
            secure_cookie = not settings.DEBUG
            response.set_cookie(
                'access_token',
                access_token,
                httponly=True,
                secure=secure_cookie,
                samesite='Lax',
                max_age=60 * 15  # 15 minutes (same as JWT access token lifetime)
            )

            return response
        else:
            return Response(
                {'detail': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
    except Usuarios.DoesNotExist:
        return Response(
            {'detail': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )

@swagger_auto_schema(method='post', tags=['Authentication'])
@api_view(['POST'])
def custom_token_logout(request):
    """Logout endpoint that clears the HttpOnly cookie"""
    response = Response({'detail': 'Successfully logged out'})
    response.delete_cookie('access_token')
    return response

@swagger_auto_schema(tags=['Direcciones'])
class DireccionesViewSet(viewsets.ModelViewSet):
    queryset = Direcciones.objects.all()
    serializer_class = DireccionesSerializer

@swagger_auto_schema(tags=['Configuración Plantel'])
class ConfiguracionPlantelViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracionPlantel.objects.all()
    serializer_class = ConfiguracionPlantelSerializer
    permission_classes = [EsAdministrador]

@swagger_auto_schema(tags=['Períodos Académicos'])
class PeriodosAcademicosViewSet(viewsets.ModelViewSet):
    queryset = PeriodosAcademicos.objects.all()
    serializer_class = PeriodosAcademicosSerializer

@swagger_auto_schema(tags=['Niveles Educativos'])
class NivelesEducativosViewSet(viewsets.ModelViewSet):
    queryset = NivelesEducativos.objects.all()
    serializer_class = NivelesEducativosSerializer

@swagger_auto_schema(tags=['Turnos'])
class TurnosViewSet(viewsets.ModelViewSet):
    queryset = Turnos.objects.all()
    serializer_class = TurnosSerializer
    permission_classes = [EsAdministrador]

@swagger_auto_schema(tags=['Grados Académicos'])
class GradosAcademicosViewSet(viewsets.ModelViewSet):
    queryset = GradosAcademicos.objects.select_related('id_nivel').all()
    serializer_class = GradosAcademicosSerializer
    permission_classes = [EsAdministrador]

@swagger_auto_schema(tags=['Secciones'])
class SeccionesViewSet(viewsets.ModelViewSet):
    queryset = Secciones.objects.all()
    serializer_class = SeccionesSerializer
    permission_classes = [EsAdministrador]

@swagger_auto_schema(tags=['Usuarios'])
class UsuariosViewSet(viewsets.ModelViewSet):
    queryset = Usuarios.objects.all()
    serializer_class = UsuariosSerializer
