from rest_framework import serializers
from .models import Profesores, RepresentantesLegales, AlumnoRepresentante
from apps.core.serializers import DireccionesSerializer, UsuariosSerializer

class ProfesoresSerializer(serializers.ModelSerializer):
    usuario_detalle = UsuariosSerializer(source='usuario', read_only=True)

    class Meta:
        model = Profesores
        fields = '__all__'

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
