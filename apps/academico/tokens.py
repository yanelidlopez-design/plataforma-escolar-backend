from django.contrib.auth.models import User
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.exceptions import AuthenticationFailed


class MiTokenRefreshSerializer(TokenRefreshSerializer):
    """
    TokenRefreshSerializer con manejo seguro de tokens huérfanos.

    Si el usuario referenciado por el token de refresco ya no existe en la
    base de datos, se responde con 401 en lugar de un 500 de Django.
    """

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except User.DoesNotExist:
            raise AuthenticationFailed(
                'El usuario asociado a este token ya no existe.',
                code='user_not_found',
            )


class MiTokenRefreshView(TokenRefreshView):
    """
    TokenRefreshView personalizada que usa el serializer de tokens
    con validación de usuarios huérfanos.
    """

    serializer_class = MiTokenRefreshSerializer