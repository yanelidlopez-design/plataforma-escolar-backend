"""
Serializers de Django REST Framework (DRF)
Plataforma Escolar Backend
"""

from rest_framework import serializers
from django.db import transaction
from .models import (
    Direccion, Alumno, RepresentanteLegal, AlumnoRepresentante,
    GrupoAcademico, Inscripcion, Calificacion, Profesor, Usuario
)


class DireccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Direccion
        fields = ['id_direccion', 'calle', 'ciudad', 'estado', 'referencia']


class RepresentanteLegalSerializer(serializers.ModelSerializer):
    direccion = DireccionSerializer(source='id_direccion_residencia', read_only=True)
    id_direccion_residencia_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = RepresentanteLegal
        fields = [
            'id_representante', 'nombres', 'apellidos', 'cedula',
            'carnet_patria', 'telefono', 'email', 'ocupacion',
            'direccion', 'id_direccion_residencia_id'
        ]

    def validate_cedula(self, value):
        request = self.context.get('request')
        instance_id = self.instance.id_representante if self.instance else None
        if RepresentanteLegal.objects.filter(cedula=value).exclude(id_representante=instance_id).exists():
            raise serializers.ValidationError("Un representante legal con esta cédula ya existe.")
        return value


class AlumnoRepresentanteSerializer(serializers.ModelSerializer):
    representante = RepresentanteLegalSerializer(source='id_representante', read_only=True)

    class Meta:
        model = AlumnoRepresentante
        fields = ['id_representante', 'parentesco', 'es_principal', 'representante']


class AlumnoDetalleSerializer(serializers.ModelSerializer):
    direccion_residencia = DireccionSerializer(source='id_direccion_residencia', read_only=True)
    representantes = serializers.SerializerMethodGetter()

    class Meta:
        model = Alumno
        fields = [
            'id_alumno', 'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'tipo_documento_identidad', 'numero_documento_identidad', 'cedula_escolar',
            'fecha_nacimiento', 'genero', 'lugar_nacimiento', 'nacionalidad',
            'entidad_federal_nacimiento', 'municipio_nacimiento', 'parroquia_nacimiento',
            'condicion_fisica', 'grupo_sanguineo', 'apoyo_escolar', 'vacunas_completas',
            'alergico_a', 'tratamiento_medico', 'peso_kg', 'talla_cm', 'talla_camisa',
            'talla_pantalon', 'talla_zapato', 'estado_civil_padres', 'ingreso_familiar',
            'profesion_madre', 'profesion_padre', 'tipo_vivienda', 'numero_hermanos',
            'numero_en_el_planter', 'discapacidad', 'tipo_discapacidad', 'observaciones',
            'fecha_inscripcion_inicial', 'estatus_general', 'direccion_residencia',
            'representantes'
        ]

    def get_representantes(self, obj):
        relaciones = AlumnoRepresentante.objects.filter(id_alumno=obj).select_related('id_representante')
        return [
            {
                'id_representante': rel.id_representante.id_representante,
                'nombres': rel.id_representante.nombres,
                'apellidos': rel.id_representante.apellidos,
                'cedula': rel.id_representante.cedula,
                'parentesco': rel.parentesco,
                'es_principal': rel.es_principal,
                'telefono': rel.id_representante.telefono,
                'email': rel.id_representante.email
            }
            for rel in relaciones
        ]


class AlumnoRegistroCompletoSerializer(serializers.ModelSerializer):
    direccion = DireccionSerializer(required=False, write_only=True)
    representante = RepresentanteLegalSerializer(required=False, write_only=True)
    parentesco = serializers.CharField(max_length=50, required=False, write_only=True, default='Padre/Madre')
    es_principal = serializers.BooleanField(required=False, write_only=True, default=True)

    class Meta:
        model = Alumno
        fields = [
            'id_alumno', 'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'tipo_documento_identidad', 'numero_documento_identidad', 'cedula_escolar',
            'fecha_nacimiento', 'genero', 'lugar_nacimiento', 'nacionalidad',
            'entidad_federal_nacimiento', 'municipio_nacimiento', 'parroquia_nacimiento',
            'condicion_fisica', 'grupo_sanguineo', 'apoyo_escolar', 'vacunas_completas',
            'alergico_a', 'tratamiento_medico', 'peso_kg', 'talla_cm', 'talla_camisa',
            'talla_pantalon', 'talla_zapato', 'estado_civil_padres', 'ingreso_familiar',
            'profesion_madre', 'profesion_padre', 'tipo_vivienda', 'numero_hermanos',
            'numero_en_el_planter', 'discapacidad', 'tipo_discapacidad', 'observaciones',
            'fecha_inscripcion_inicial', 'estatus_general', 'direccion', 'representante',
            'parentesco', 'es_principal'
        ]

    def validate_numero_documento_identidad(self, value):
        if Alumno.objects.filter(numero_documento_identidad=value).exists():
            raise serializers.ValidationError("Un estudiante con este número de documento ya está registrado.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        direccion_data = validated_data.pop('direccion', None)
        representante_data = validated_data.pop('representante', None)
        parentesco = validated_data.pop('parentesco', 'Padre/Madre')
        es_principal = validated_data.pop('es_principal', True)

        # 1. Crear Dirección de Residencia si aplica
        direccion_obj = None
        if direccion_data:
            direccion_obj = Direccion.objects.create(**direccion_data)
            validated_data['id_direccion_residencia'] = direccion_obj

        # 2. Crear Alumno
        alumno = Alumno.objects.create(**validated_data)

        # 3. Crear o Vincular Representante Legal
        if representante_data:
            cedula_rep = representante_data.get('cedula')
            rep_obj = RepresentanteLegal.objects.filter(cedula=cedula_rep).first()
            if not rep_obj:
                rep_obj = RepresentanteLegal.objects.create(**representante_data)

            # 4. Crear relación Alumno - Representante
            AlumnoRepresentante.objects.create(
                id_alumno=alumno,
                id_representante=rep_obj,
                parentesco=parentesco,
                es_principal=es_principal
            )

        return alumno


class InscripcionSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.ReadOnlyField(source='id_alumno.__str__')
    grupo_info = serializers.ReadOnlyField(source='id_grupo.__str__')

    class Meta:
        model = Inscripcion
        fields = [
            'id_inscripcion', 'id_alumno', 'id_grupo', 'fecha_inscripcion',
            'estado_inscripcion', 'monto_pago', 'referencia_bancaria',
            'alumno_nombre', 'grupo_info'
        ]


class CalificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calificacion
        fields = [
            'id_calificacion', 'id_inscripcion', 'id_profesor',
            'calificacion', 'fecha_registro'
        ]
