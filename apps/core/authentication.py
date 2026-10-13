from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from .models import Usuarios


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