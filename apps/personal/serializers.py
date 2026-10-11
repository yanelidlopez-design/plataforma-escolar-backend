from rest_framework import serializers
from .models import Profesores, RepresentantesLegales, AlumnoRepresentante
from apps.core.serializers import DireccionesSerializer, UsuariosSerializer

class ProfesoresSerializer(serializers.ModelSerializer):
    # El FK del modelo se llama 'id_usuario' -> el source correcto es 'id_usuario'.
    usuario_detalle = UsuariosSerializer(source='id_usuario', read_only=True)
    # Validación estricta del POST: solo las 7 categorías permitidas
    categoria = serializers.ChoiceField(choices=Profesores.CATEGORIA_CHOICES)

    class Meta:
        model = Profesores
        # id_usuario se crea automáticamente en perform_create cuando no viene en el payload.
        fields = '__all__'
        extra_kwargs = {
            'id_usuario': {'required': False},
        }

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
