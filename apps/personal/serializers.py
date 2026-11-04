from django.db import transaction
from rest_framework import serializers

from .models import HijosPersonal, Profesores, RepresentantesLegales, AlumnoRepresentante
from apps.core.serializers import DireccionesSerializer, UsuariosSerializer


class HijoPersonalSerializer(serializers.ModelSerializer):
    edad = serializers.IntegerField(min_value=0, max_value=120)

    class Meta:
        model = HijosPersonal
        fields = ('primer_nombre', 'segundo_nombre', 'edad')


class ProfesoresSerializer(serializers.ModelSerializer):
    # El FK del modelo se llama 'id_usuario' -> el source correcto es 'id_usuario'.
    usuario_detalle = UsuariosSerializer(source='id_usuario', read_only=True)
    # Validación estricta del POST: solo los cargos permitidos
    cargo = serializers.ChoiceField(choices=Profesores.CARGO_CHOICES, required=False)
    # Propiedades calculadas (solo lectura)
    edad = serializers.SerializerMethodField(read_only=True)
    tiempo_servicio = serializers.SerializerMethodField(read_only=True)
    hijos = HijoPersonalSerializer(many=True, required=False)

    class Meta:
        model = Profesores
        # id_usuario se crea automáticamente en perform_create cuando no viene en el payload.
        fields = '__all__'
        extra_kwargs = {
            'id_usuario': {'required': False},
        }

    def validate(self, attrs):
        hijos = attrs.get('hijos')
        numero_hijos = attrs.get(
            'numero_hijos',
            getattr(self.instance, 'numero_hijos', None),
        )
        if hijos and numero_hijos is not None and len(hijos) > numero_hijos:
            raise serializers.ValidationError({
                'hijos': 'No puede registrar más detalles que el número de hijos indicado.'
            })
        if hijos and numero_hijos is None:
            raise serializers.ValidationError({
                'numero_hijos': 'Indique el número de hijos para guardar sus datos.'
            })
        return attrs

    def get_edad(self, obj):
        return obj.edad

    def get_tiempo_servicio(self, obj):
        return obj.tiempo_servicio

    @transaction.atomic
    def update(self, instance, validated_data):
        hijos = validated_data.pop('hijos', None)
        instance = super().update(instance, validated_data)
        if hijos is not None:
            instance.hijos.all().delete()
            HijosPersonal.objects.bulk_create([
                HijosPersonal(personal=instance, **hijo)
                for hijo in hijos
            ])
        return instance


class RepresentantesLegalesSerializer(serializers.ModelSerializer):
    direccion_detalle = DireccionesSerializer(source='direccion', read_only=True)

    class Meta:
        model = RepresentantesLegales
        fields = '__all__'

class AlumnoRepresentanteSerializer(serializers.ModelSerializer):
    representante_detalle = RepresentantesLegalesSerializer(source='representante', read_only=True)

    class Meta:
        model = AlumnoRepresentante
        fields = '__all__'
