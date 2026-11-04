from django.conf import settings
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.exceptions import AuthenticationFailed, TokenError


class MiTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Refresco de tokens validado contra core.Usuarios (no auth.User).

    El login (custom_token_obtain) emite tokens con user_id = Usuarios.id_usuario.
    La versión base de simplejwt (5.5) busca el usuario en get_user_model()
    (auth.User), cuyas claves no coinciden: el refresh devolvía 401 o
    autenticaba al usuario equivocado. Aquí se exige además que el usuario
    siga activo.
    """

    def validate(self, attrs):
        from apps.core.models import Usuarios

        try:
            refresh = self.token_class(attrs['refresh'])
        except TokenError:
            raise AuthenticationFailed(
                self.error_messages['no_active_account'], 'no_active_account'
            )

        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        try:
            user = Usuarios.objects.get(id_usuario=user_id, activo=True) if user_id else None
        except (Usuarios.DoesNotExist, ValueError, TypeError):
            user = None

        if not user:
            raise AuthenticationFailed(
                self.error_messages['no_active_account'], 'no_active_account'
            )

        # ROTATE_REFRESH_TOKENS no está habilitado en el proyecto; si se
        # activa, replicar aquí la rotación/blacklist de la clase base.
        return {'access': str(refresh.access_token)}


class MiTokenRefreshView(TokenRefreshView):
    """
    TokenRefreshView personalizada que usa el serializer de tokens
    con validación de usuarios huérfanos.

    Además setea el access renovado como cookie HttpOnly `access_token`
    (el body también incluye 'access' por si el cliente usa Bearer).
    """

    serializer_class = MiTokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        access = response.data.get('access')
        if access:
            response.set_cookie(
                'access_token',
                access,
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
                max_age=60 * 15,
            )
        return response


class MiTokenRefreshView(TokenRefreshView):
    """
    TokenRefreshView personalizada que usa el serializer de tokens
    con validación de usuarios huérfanos.

    Además setea el access renovado como cookie HttpOnly `access_token`
    (el body también incluye 'access' por si el cliente usa Bearer).
    """

    serializer_class = MiTokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        access = response.data.get('access')
        if access:
            response.set_cookie(
                'access_token',
                access,
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
                max_age=60 * 15,
            )
        return response