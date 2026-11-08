from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework.authentication import BaseAuthentication

from .models import Usuarios
from apps.academico.models import PeriodoCalificacion, ConfiguracionAsistenciaPublica


class UsuariosJWTAuthentication(JWTAuthentication):
    """
    Autenticación JWT contra el modelo `core.Usuarios` (no `auth.User`).

    El endpoint de login (`custom_token_obtain`) emite tokens con
    `user_id = Usuarios.id_usuario`, pero la clase base `JWTAuthentication`
    valida contra `get_user_model()` (`auth.User`), cuyas claves no
    coinciden: todo request autenticado devolvía 401 "User not found".
    Además, acepta el access_token desde la cookie HttpOnly `access_token`
    que emite el login, además de la cabecera `Authorization: Bearer`.
    """

    cookie_name = 'access_token'

    def authenticate(self, request):
        header = self.get_header(request)

        if header is None:
            # Sin cabecera Authorization: intentar la cookie HttpOnly del login.
            cookie_token = request.COOKIES.get(self.cookie_name)
            if not cookie_token:
                return None
            raw_token = cookie_token.encode('utf-8')
        else:
            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token

    def get_user(self, validated_token):
        user_id = validated_token.get('user_id')
        if user_id is None:
            raise AuthenticationFailed(
                _('Token inválido: no contiene user_id.'),
                code='user_not_found',
            )

        try:
            return Usuarios.objects.get(id_usuario=user_id, activo=True)
        except Usuarios.DoesNotExist:
            raise AuthenticationFailed(
                _('Usuario no encontrado o inactivo.'),
                code='user_not_found',
            )


class TokenDocenteUser:
    """
    Usuario simulado autenticado mediante token temporal de carga de notas.
    Tiene is_authenticated = True para superar permisos de IsAuthenticated en DRF.
    """
    is_authenticated = True
    is_anonymous = False
    is_active = True

    def __init__(self, periodo):
        self.token_periodo = periodo
        self.username = f"docente_token_{periodo.pk}"
        self.pk = None

    def __str__(self):
        return self.username


class URLTokenAuthentication(BaseAuthentication):
    """
    Autenticación por token en parámetros de URL para formularios externos
    de carga de notas.

    Lee el token desde:
      1. Query param `?token=...`
      2. Cabecera `Authorization: Bearer <token>`

    Valida el token contra `PeriodoCalificacion.token_acceso`.
    """

    def authenticate(self, request):
        # Intento 1: query param ?token=... (funciona con request DRF o WSGIRequest)
        query_dict = getattr(request, 'query_params', getattr(request, 'GET', {}))
        token = query_dict.get('token')

        # Intento 2: cabecera Authorization: Bearer <token>
        if not token:
            auth_header = getattr(request, 'headers', {}).get(
                'Authorization', request.META.get('HTTP_AUTHORIZATION', '')
            )
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1].strip()

        if not token:
            return None

        # Validar contra PeriodoCalificacion
        try:
            periodo = PeriodoCalificacion.objects.get(
                token_acceso=token,
                activo_manual=True,
            )
        except PeriodoCalificacion.DoesNotExist:
            raise AuthenticationFailed(
                _('Token de acceso inválido o expirado.'),
                code='invalid_token',
            )

        if not periodo.esta_abierto():
            raise AuthenticationFailed(
                _('El periodo de calificación está cerrado.'),
                code='periodo_cerrado',
            )

        # Crear un usuario autenticado por token con is_authenticated = True
        user = TokenDocenteUser(periodo)
        return (user, token)


class URLTokenAsistenciaAuthentication(BaseAuthentication):
    """
    Autenticación por token en parámetros de URL para el formulario público
    de toma de asistencia.

    Lee el token desde:
      1. Query param ?token=...
      2. Cabecera Authorization: Bearer <token>

    Valida el token contra ConfiguracionAsistenciaPublica.token_acceso.
    """

    def authenticate(self, request):
        query_dict = getattr(request, 'query_params', getattr(request, 'GET', {}))
        token = query_dict.get('token')

        if not token:
            auth_header = getattr(request, 'headers', {}).get(
                'Authorization', request.META.get('HTTP_AUTHORIZATION', '')
            )
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1].strip()

        if not token:
            return None

        try:
            config = ConfiguracionAsistenciaPublica.objects.get(
                token_acceso=token,
                activo=True,
            )
        except ConfiguracionAsistenciaPublica.DoesNotExist:
            raise AuthenticationFailed(
                _('Token de acceso inválido o inactivo.'),
                code='invalid_token',
            )

        # Usuario simulado autenticado por token público de asistencia
        user = TokenDocenteUser(config)
        user.username = f"asistencia_token_{config.id_config}"
        return (user, token)