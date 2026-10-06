from rest_framework import serializers
from .models import Alumnos, GruposAcademicos, Inscripciones, Calificaciones, Asistencias
from apps.core.serializers import DireccionesSerializer, PeriodosAcademicosSerializer, GradosAcademicosSerializer, SeccionesSerializer, TurnosSerializer
from apps.personal.serializers import ProfesoresSerializer

class AlumnosSerializer(serializers.ModelSerializer):
    direccion_detalle = DireccionesSerializer(source='id_direccion_residencia', read_only=True)

    class Meta:
        model = Alumnos
        fields = '__all__'

    def validate_peso_kg(self, value):
        if value is not None and (value < 10 or value > 200):
            raise serializers.ValidationError("El peso debe estar entre 10 y 200 kg")
        return value

    def validate_talla_cm(self, value):
        if value is not None and (value < 50 or value > 250):
            raise serializers.ValidationError("La talla debe estar entre 50 y 250 cm")
        return value

    def validate_talla_zapato(self, value):
        if value is not None and (value < 20 or value > 50):
            raise serializers.ValidationError("La talla de zapato debe estar entre 20 y 50")
        return value

class GruposAcademicosSerializer(serializers.ModelSerializer):
    periodo_detalle = PeriodosAcademicosSerializer(source='periodo', read_only=True)
    grado_detalle = GradosAcademicosSerializer(source='grado', read_only=True)
    seccion_detalle = SeccionesSerializer(source='seccion', read_only=True)
    turno_detalle = TurnosSerializer(source='turno', read_only=True)
    profesor_guia_detalle = ProfesoresSerializer(source='profesor_director', read_only=True)

    class Meta:
        model = GruposAcademicos
        fields = '__all__'

class InscripcionesSerializer(serializers.ModelSerializer):
    fecha_inscripcion = serializers.DateTimeField(format="%Y-%m-%d", input_formats=["%Y-%m-%d", "iso-8601"], allow_null=True, required=False)
    alumno_detalle = AlumnosSerializer(source='alumno', read_only=True)
    grupo_academico_detalle = GruposAcademicosSerializer(source='grupo', read_only=True)
    periodo_detalle = PeriodosAcademicosSerializer(source='grupo.id_periodo', read_only=True)

    class Meta:
        model = Inscripciones
        fields = '__all__'

class CalificacionesSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.ReadOnlyField(source='inscripcion.id_alumno.primer_nombre')
    alumno_apellido = serializers.ReadOnlyField(source='inscripcion.id_alumno.primer_apellido')
    profesor_nombre = serializers.ReadOnlyField(source='id_profesor.primer_nombre')

    class Meta:
        model = Calificaciones
        fields = '__all__'

    def validate_calificacion(self, value):
        opciones_validas = ['A', 'B', 'C', 'D']
        if value not in opciones_validas:
            raise serializers.ValidationError(f"La calificación debe ser una de las siguientes opciones: {opciones_validas}")
        return value

class AsistenciasSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.ReadOnlyField(source='alumno.primer_nombre')
    alumno_apellido = serializers.ReadOnlyField(source='alumno.primer_apellido')
    alumno_cedula = serializers.ReadOnlyField(source='alumno.cedula_escolar')
    grupo_nombre = serializers.ReadOnlyField(source='grupo.id_grado.nombre_grado')
    seccion_nombre = serializers.ReadOnlyField(source='grupo.id_seccion.nombre_seccion')
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Asistencias
        fields = '__all__'

    def validate_estado(self, value):
        opciones_validas = ['P', 'A', 'J']
        if value not in opciones_validas:
            raise serializers.ValidationError(f"El estado debe ser una de las siguientes opciones: {opciones_validas}")
        return value
