from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from .models import (
    Direcciones, ConfiguracionPlantel, PeriodosAcademicos,
    NivelesEducativos, Turnos, GradosAcademicos, Secciones, Usuarios
)


def _validate_password(value, user=None):
    try:
        validate_password(value, user=user)
    except DjangoValidationError as error:
        raise serializers.ValidationError(error.messages) from error


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
    clave_hash = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Usuarios
        fields = '__all__'

    def validate_clave_hash(self, value):
        _validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('clave_hash', None)
        if not password:
            raise serializers.ValidationError({
                'clave_hash': 'Debe indicar una contraseña.'
            })
        usuario = Usuarios(**validated_data)
        usuario.set_password(password)
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        password = validated_data.pop('clave_hash', None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class CambioContrasenaSerializer(serializers.Serializer):
    contrasena_actual = serializers.CharField(write_only=True, trim_whitespace=False)
    contrasena_nueva = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=8,
    )
    confirmar_contrasena = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs['contrasena_nueva'] != attrs['confirmar_contrasena']:
            raise serializers.ValidationError({
                'confirmar_contrasena': 'La confirmación no coincide con la nueva contraseña.'
            })
        _validate_password(attrs['contrasena_nueva'], self.context.get('user'))
        return attrs


class RestablecerContrasenaSerializer(serializers.Serializer):
    contrasena_nueva = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=8,
    )
    confirmar_contrasena = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs['contrasena_nueva'] != attrs['confirmar_contrasena']:
            raise serializers.ValidationError({
                'confirmar_contrasena': 'La confirmación no coincide con la nueva contraseña.'
            })
        _validate_password(attrs['contrasena_nueva'], self.context.get('user'))
        return attrs


class SolicitarRestablecimientoSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ConfirmarRestablecimientoSerializer(RestablecerContrasenaSerializer):
    uid = serializers.CharField(write_only=True, trim_whitespace=False)
    token = serializers.CharField(write_only=True, trim_whitespace=False)


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
