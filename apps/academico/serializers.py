from django.db import transaction
from rest_framework import serializers
from .models import Alumnos, GruposAcademicos, Inscripciones, Calificaciones, Asistencias
from apps.core.serializers import DireccionesSerializer, PeriodosAcademicosSerializer, GradosAcademicosSerializer, SeccionesSerializer, TurnosSerializer
from apps.personal.serializers import ProfesoresSerializer
from apps.personal.models import RepresentantesLegales, AlumnoRepresentante


class RepresentanteAnidadoSerializer(serializers.Serializer):
    """
    Datos del representante legal anidados dentro de la creación de un alumno.
    JSON conceptual:
    {
      "representante": {"cedula": "V-REMOVED_SECRET78", "nombre": "Pedro Perez", "telefono": "0412REMOVED_SECRET7"},
      "parentesco": "Padre"
    }
    """
    cedula = serializers.CharField(max_length=20, required=True)
    nombre = serializers.CharField(max_length=200, required=True)  # Nombre completo
    telefono = serializers.CharField(max_length=20, required=True)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)


class AlumnosSerializer(serializers.ModelSerializer):
    direccion_detalle = DireccionesSerializer(source='id_direccion_residencia', read_only=True)
    representante = RepresentanteAnidadoSerializer(required=False, allow_null=True)
    parentesco = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=50,
        help_text='Parentesco del representante con el alumno (requiere "representante").'
    )

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

    def to_representation(self, instance):
        """
        En la respuesta incluye los datos del representante vinculado (si existe)
        para poder precargar el formulario en modo edición:
        alumno.representante.cedula / alumno.representante.nombre / alumno.parentesco
        """
        data = super().to_representation(instance)
        relacion = instance.representantes_vinculados.first()

        if relacion and relacion.representante:
            rep = relacion.representante
            data['representante'] = {
                'cedula': rep.cedula,
                'nombre': f'{rep.primer_nombre} {rep.primer_apellido}'.strip(),
                'telefono': rep.telefono_principal,
                'email': rep.email or '',
            }
            data['parentesco'] = relacion.parentesco or ''
        else:
            data['representante'] = None
            data['parentesco'] = None
        return data

    def validate(self, attrs):
        """El parentesco solo tiene sentido si se envían los datos del representante."""
        if attrs.get('parentesco') and not attrs.get('representante'):
            raise serializers.ValidationError(
                {'representante': 'Debe indicar los datos del representante si envía el parentesco.'}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """
        Crea el alumno y, de forma atómica, el representante (si no existe por cédula)
        y la relación pivot AlumnoRepresentante con su parentesco.
        """
        representante_data = validated_data.pop('representante', None)
        parentesco = validated_data.pop('parentesco', None)

        alumno = Alumnos.objects.create(**validated_data)

        if representante_data:
            self._vincular_representante(alumno, representante_data, parentesco)

        return alumno

    @transaction.atomic
    def update(self, instance, validated_data):
        representante_data = validated_data.pop('representante', None)
        parentesco = validated_data.pop('parentesco', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if representante_data:
            self._vincular_representante(instance, representante_data, parentesco)

        return instance

    @staticmethod
    def _vincular_representante(alumno, representante_data, parentesco):
        """
        Vincula un alumno con su representante legal:
        - Si la cédula ya existe en representantes_legales, la reutiliza (get_or_create).
        - Si no existe, crea el registro.
        - Crea/actualiza la fila pivot en alumno_representante (PK compuesta id_alumno).
        """
        # 'nombre' llega completo ("Pedro Perez") y se expande a primer_nombre/primer_apellido
        # porque la tabla legacy exige ambos campos NOT NULL.
        partes = representante_data['nombre'].split()
        primer_nombre = partes[0]
        primer_apellido = ' '.join(partes[1:]) if len(partes) > 1 else 'S/I'

        representante, _creado = RepresentantesLegales.objects.get_or_create(
            cedula=representante_data['cedula'],
            defaults={
                'primer_nombre': primer_nombre,
                'primer_apellido': primer_apellido,
                'telefono_principal': representante_data['telefono'],
                'email': representante_data.get('email') or None,
            },
        )

        # update_or_create: la relación usa id_alumno como PK (un solo representante
        # por alumno en esta tabla pivot), así la operación es idempotente.
        AlumnoRepresentante.objects.update_or_create(
            alumno=alumno,
            defaults={
                'representante': representante,
                'parentesco': parentesco or None,
                'es_principal': True,
            },
        )

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
