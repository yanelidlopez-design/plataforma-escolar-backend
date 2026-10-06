from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    Direcciones, ConfiguracionPlantel, PeriodosAcademicos,
    NivelesEducativos, Turnos, GradosAcademicos, Secciones, Usuarios
)

# Model Serializers
class DireccionesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Direcciones
        fields = '__all__'

class ConfiguracionPlantelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionPlantel
        fields = '__all__'

class PeriodosAcademicosSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodosAcademicos
        fields = '__all__'

class NivelesEducativosSerializer(serializers.ModelSerializer):
    class Meta:
        model = NivelesEducativos
        fields = '__all__'

class TurnosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Turnos
        fields = '__all__'

class GradosAcademicosSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradosAcademicos
        fields = '__all__'

class SeccionesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Secciones
        fields = '__all__'

class UsuariosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuarios
        fields = '__all__'
        extra_kwargs = {
            'clave_hash': {'write_only': True}
        }

# JWT Custom Serializer
User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # The parent class expects 'username', but we're receiving 'nombre_usuario'
        # or whatever the USERNAME_FIELD is
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            try:
                user = User.objects.get(**{User.USERNAME_FIELD: username})
                if user.check_password(password):
                    attrs['user'] = user
                    return super().validate(attrs)
            except User.DoesNotExist:
                pass

        from rest_framework.exceptions import AuthenticationFailed
        raise AuthenticationFailed('Invalid credentials')


class CustomBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(**{User.USERNAME_FIELD: username})
        except ObjectDoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


class CustomBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(**{User.USERNAME_FIELD: username})
        except ObjectDoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


