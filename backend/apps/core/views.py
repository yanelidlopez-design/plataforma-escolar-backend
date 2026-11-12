from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import viewsets, permissions, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.decorators import (
    action, api_view, authentication_classes, permission_classes, throttle_classes,
)
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from drf_yasg.utils import swagger_auto_schema
from .models import (
    Direcciones, ConfiguracionPlantel, PeriodosAcademicos,
    NivelesEducativos, Turnos, GradosAcademicos, Secciones, Usuarios
)
from .serializers import (
    DireccionesSerializer, ConfiguracionPlantelSerializer, PeriodosAcademicosSerializer,
    NivelesEducativosSerializer, TurnosSerializer, GradosAcademicosSerializer,
    SeccionesSerializer, UsuariosSerializer, CambioContrasenaSerializer,
    SolicitarRestablecimientoSerializer, ConfirmarRestablecimientoSerializer,
    CustomTokenObtainPairSerializer,
)

# Permisos globales para los conjuntos de vistas de control del plantel
from apps.academico.permissions import EsAdministrador
from apps.academico.models import ConfiguracionAsistenciaPublica
from apps.academico.serializers import ConfiguracionAsistenciaPublicaSerializer

@swagger_auto_schema(method='post', tags=['Authentication'])
@api_view(['POST'])
@authentication_classes([])
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


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    TokenObtainPairView basada en clase para core.Usuarios.

    Usa CustomTokenObtainPairSerializer (acepta 'username' o 'nombre_usuario',
    busca por nombre_usuario o email, verifica con check_password).
    Además setea el access_token como cookie HttpOnly, igual que el endpoint
    function-based custom_token_obtain.
    """

    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed:
            return Response(
                {'detail': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        data = serializer.validated_data
        user = serializer.user

        response = Response({
            'access': data['access'],
            'refresh': data.get('refresh'),
            'user': {
                'username': user.nombre_usuario,
                'id_usuario': user.id_usuario,
                'activo': user.activo,
            },
        })

        secure_cookie = not settings.DEBUG
        response.set_cookie(
            'access_token',
            data['access'],
            httponly=True,
            secure=secure_cookie,
            samesite='Lax',
            max_age=60 * 15,  # 15 minutes (same as JWT access token lifetime)
        )
        return response


@swagger_auto_schema(method='post', tags=['Authentication'])
@api_view(['POST'])
def custom_token_logout(request):
    """Logout endpoint that clears the HttpOnly cookie"""
    response = Response({'detail': 'Successfully logged out'})
    response.delete_cookie('access_token')
    return response


class UsuariosPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{user.clave_hash}{timestamp}{user.email}'


password_reset_token_generator = UsuariosPasswordResetTokenGenerator()


class PasswordResetThrottle(AnonRateThrottle):
    scope = 'password_reset'


@swagger_auto_schema(method='post', tags=['Authentication'])
@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@throttle_classes([PasswordResetThrottle])
def solicitar_restauracion_contrasena(request):
    serializer = SolicitarRestablecimientoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email']

    usuarios = Usuarios.objects.filter(email__iexact=email, activo=True)
    if usuarios.count() == 1:
        usuario = usuarios.get()
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = password_reset_token_generator.make_token(usuario)
        query = urlencode({'uid': uid, 'token': token})
        frontend_url = settings.FRONTEND_URL.rstrip('/')
        if frontend_url:
            reset_url = f'{frontend_url}/recuperar-contrasena?{query}'
        else:
            reset_url = request.build_absolute_uri(f'/recuperar-contrasena?{query}')
        send_mail(
            'Restablece tu contraseña de Plataforma Escolar',
            (
                'Recibimos una solicitud para restablecer la contraseña de tu cuenta. '
                f'Usa este enlace dentro de una hora: {reset_url}\n\n'
                'Si no solicitaste este cambio, puedes ignorar este mensaje.'
            ),
            settings.DEFAULT_FROM_EMAIL,
            [usuario.email],
        )

    return Response(
        {
            'detail': (
                'Si el correo está asociado a una cuenta activa, recibirás '
                'instrucciones para restablecer la contraseña.'
            )
        },
        status=status.HTTP_202_ACCEPTED,
    )


@swagger_auto_schema(method='post', tags=['Authentication'])
@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def confirmar_restauracion_contrasena(request):
    serializer = ConfirmarRestablecimientoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        uid = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))
        usuario = Usuarios.objects.get(pk=uid, activo=True)
    except (TypeError, ValueError, OverflowError, Usuarios.DoesNotExist):
        return Response(
            {'token': ['El enlace no es válido o ha expirado.']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not password_reset_token_generator.check_token(
        usuario, serializer.validated_data['token']
    ):
        return Response(
            {'token': ['El enlace no es válido o ha expirado.']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    usuario.set_password(serializer.validated_data['contrasena_nueva'])
    usuario.save(update_fields=['clave_hash'])
    return Response(
        {'detail': 'Contraseña restablecida correctamente.'},
        status=status.HTTP_200_OK,
    )


@swagger_auto_schema(tags=['Direcciones'])
class DireccionesViewSet(viewsets.ModelViewSet):
    queryset = Direcciones.objects.all()
    serializer_class = DireccionesSerializer
    permission_classes = [EsAdministrador]


@swagger_auto_schema(tags=['Configuración Plantel'])
class ConfiguracionPlantelViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracionPlantel.objects.all()
    serializer_class = ConfiguracionPlantelSerializer
    permission_classes = [EsAdministrador]


@swagger_auto_schema(tags=['Periodos Académicos'])
class PeriodosAcademicosViewSet(viewsets.ModelViewSet):
    queryset = PeriodosAcademicos.objects.all()
    serializer_class = PeriodosAcademicosSerializer
    permission_classes = [EsAdministrador]


@swagger_auto_schema(tags=['Niveles Educativos'])
class NivelesEducativosViewSet(viewsets.ModelViewSet):
    queryset = NivelesEducativos.objects.all()
    serializer_class = NivelesEducativosSerializer
    permission_classes = [EsAdministrador]


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
    permission_classes = [EsAdministrador]

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Return the authenticated user without exposing password data."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['post'],
        url_path='cambiar-password',
        permission_classes=[permissions.IsAuthenticated],
    )
    def cambiar_password(self, request):
        serializer = CambioContrasenaSerializer(
            data=request.data,
            context={'user': request.user},
        )
        serializer.is_valid(raise_exception=True)
        usuario = request.user

        if not hasattr(usuario, 'check_password') or not hasattr(usuario, 'set_password'):
            return Response(
                {'detail': 'La cuenta autenticada no permite cambiar su contraseña aquí.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not usuario.check_password(serializer.validated_data['contrasena_actual']):
            return Response(
                {'contrasena_actual': ['La contraseña actual es incorrecta.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if usuario.check_password(serializer.validated_data['contrasena_nueva']):
            return Response(
                {'contrasena_nueva': ['La nueva contraseña debe ser diferente a la actual.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario.set_password(serializer.validated_data['contrasena_nueva'])
        usuario.save(update_fields=['clave_hash'])
        return Response({'detail': 'Contraseña actualizada correctamente.'})


@swagger_auto_schema(tags=['Configuración Asistencia Pública'])
class ConfiguracionAsistenciaPublicaViewSet(viewsets.ModelViewSet):
    """CRUD para la configuración de enlace público de asistencia.
    Sólo admin (staff) puede crear/editar. Lectura pública restringida a usuarios autenticados.
    """
    queryset = ConfiguracionAsistenciaPublica.objects.all()
    serializer_class = ConfiguracionAsistenciaPublicaSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]


@swagger_auto_schema(method='get', tags=['Asistencia Pública'])
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def asistencia_publica_link(request):
    """Endpoint público que devuelve el enlace activo del día.
    - Busca la configuración de hoy marcada como `activo=True`.
    - Si no hay ninguna, responde 404.
    - Retorna la URL completa (frontend + token) y el token.
    """
    today = timezone.localdate()
    try:
        config = ConfiguracionAsistenciaPublica.objects.get(fecha_dia=today, activo=True)
    except ConfiguracionAsistenciaPublica.DoesNotExist:
        return Response({'detail': 'No hay enlace activo para hoy'}, status=404)

    public_url = f"{settings.FRONTEND_URL.rstrip('/')}/asistencia/{config.token_acceso}"
    return Response({
        'url': public_url,
        'token': config.token_acceso,
        'fecha_dia': config.fecha_dia,
    })


@swagger_auto_schema(method='get', tags=['Asistencia Pública'])
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def asistencia_publica_redirect(request, token):
    """Redirige al frontend a la página de toma de asistencia pública."""
    public_url = f"{settings.FRONTEND_URL.rstrip('/')}/asistencia/{token}"
    return redirect(public_url)
