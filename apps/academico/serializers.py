import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from .models import (
    Alumnos,
    GruposAcademicos,
    Inscripciones,
    Calificaciones,
    Asistencias,
    PeriodoInscripcion,
    CalificacionLiteral,
    PeriodoCalificacion,
)
from apps.core.serializers import DireccionesSerializer, PeriodosAcademicosSerializer, GradosAcademicosSerializer, SeccionesSerializer, TurnosSerializer
from apps.core.models import Direcciones
from apps.personal.serializers import ProfesoresSerializer
from apps.personal.models import RepresentantesLegales, AlumnoRepresentante


logger = logging.getLogger(__name__)


class RepresentanteAnidadoSerializer(serializers.Serializer):
    """
    Datos del representante legal anidados dentro de la creación de un alumno.
    JSON conceptual:
    {
      "representante": {"cedula": "V-19888777", "nombre": "Pedro Perez", "telefono": "04125555555"},
      "parentesco": "Padre"
    }
    """
    cedula = serializers.CharField(max_length=20, required=True)
    nombre = serializers.CharField(max_length=200, required=True)  # Nombre completo
    telefono = serializers.CharField(max_length=20, required=True)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)


class DireccionAnidadaSerializer(serializers.Serializer):
    """
    Dirección de residencia del alumno anidada en el payload del alumno.
    Se persiste en core.Direcciones y se vincula vía alumnos.id_direccion_residencia.
    """
    calle = serializers.CharField(max_length=255, required=True)
    ciudad = serializers.CharField(max_length=100, required=True)
    estado = serializers.CharField(max_length=100, required=True)
    referencia = serializers.CharField(required=False, allow_null=True, allow_blank=True, default='')


class AlumnosSerializer(serializers.ModelSerializer):
    direccion_detalle = DireccionesSerializer(source='id_direccion_residencia', read_only=True)
    representante = RepresentanteAnidadoSerializer(required=False, allow_null=True)
    parentesco = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=50,
        help_text='Parentesco del representante con el alumno (requiere "representante").'
    )
    direccion = DireccionAnidadaSerializer(
        required=False, allow_null=True,
        help_text='Dirección de residencia del alumno (se crea/actualiza en core.Direcciones).'
    )
    # Grupo académico: se asigna vía inscripción activa (create/update de la inscripción).
    id_grupo = serializers.IntegerField(
        required=False, allow_null=True, write_only=True,
        help_text='ID del grupo académico; crea/actualiza la inscripción activa del alumno.'
    )
    grupo_inscripcion_id = serializers.SerializerMethodField()
    # Campos adicionales para display en la UI (grado/seccion/profesor encargado)
    grado_actual = serializers.SerializerMethodField()
    seccion_actual = serializers.SerializerMethodField()
    profesor_encargado = serializers.SerializerMethodField()

    class Meta:
        model = Alumnos
        fields = '__all__'

    def to_internal_value(self, data):
        """
        Normaliza cédula escolar vacía a NULL antes de las validaciones de campo:
        la columna es UNIQUE y '' duplicado rechazaría el guardado con 400.
        """
        if isinstance(data, dict) and data.get('cedula_escolar') == '':
            data = {**data, 'cedula_escolar': None}
        return super().to_internal_value(data)

    def get_grado_actual(self, obj):
        """Obtiene el nivel actual (grado/seccion) del alumno a través de Inscripciones activas."""
        try:
            inscripcion = obj.inscripciones.filter(estado_inscripcion__in=['Activa', 'Graduado']).first()
            if inscripcion and inscripcion.grupo:
                return inscripcion.grupo.grado.nombre_grado if hasattr(inscripcion.grupo.grado, 'nombre_grado') else str(inscripcion.grupo.grado)
        except Exception:
            logger.debug('Campo derivado no disponible para alumno %s', obj.pk, exc_info=True)
        return None

    def get_seccion_actual(self, obj):
        """Obtiene la sección actual del alumno a través de Inscripciones activas."""
        try:
            inscripcion = obj.inscripciones.filter(estado_inscripcion__in=['Activa', 'Graduado']).first()
            if inscripcion and inscripcion.grupo:
                return inscripcion.grupo.seccion.nombre_seccion if hasattr(inscripcion.grupo.seccion, 'nombre_seccion') else str(inscripcion.grupo.seccion)
        except Exception:
            logger.debug('Campo derivado no disponible para alumno %s', obj.pk, exc_info=True)
        return None

    def get_profesor_encargado(self, obj):
        """Profesor encargado (Docente Guía) del alumno.
        1) Asignación directa: FK id_profesor_encargado en la tabla alumnos.
        2) Fallback: vía inscripción activa -> grupo -> profesor director.
        """
        try:
            if obj.id_profesor_encargado:
                return f"{obj.id_profesor_encargado.primer_nombre} {obj.id_profesor_encargado.primer_apellido}".strip()
        except Exception:
            logger.debug('Campo derivado no disponible para alumno %s', obj.pk, exc_info=True)
        try:
            inscripcion = obj.inscripciones.filter(estado_inscripcion__in=['Activa', 'Graduado']).first()
            if inscripcion and inscripcion.grupo and inscripcion.grupo.profesor_director:
                profesor = inscripcion.grupo.profesor_director
                return f"{profesor.primer_nombre} {profesor.primer_apellido}"
        except Exception:
            logger.debug('Campo derivado no disponible para alumno %s', obj.pk, exc_info=True)
        return None

    def get_grupo_inscripcion_id(self, obj):
        """ID del grupo de la inscripción activa del alumno (para precargar el form)."""
        try:
            inscripcion = obj.inscripciones.filter(estado_inscripcion='Activa').first()
            return inscripcion.grupo_id if inscripcion else None
        except Exception:
            return None

    def validate_id_grupo(self, value):
        if value is not None and not GruposAcademicos.objects.filter(pk=value).exists():
            raise serializers.ValidationError("El grupo indicado no existe.")
        return value

    def validate_peso_kg(self, value):
        if value is not None and (value < 10 or value > 200):
            raise serializers.ValidationError("El peso debe estar entre 10 y 200 kg")
        return value

    def validate_talla_cm(self, value):
        if value is not None and (value < 50 or value > 250):
            raise serializers.ValidationError("La talla debe estar entre 50 y 250 cm")
        return value

    def validate_talla_zapato(self, value):
        # El modelo almacena la talla como texto ('32'), por eso llega como str.
        if value not in (None, ''):
            try:
                n = float(value)
            except (TypeError, ValueError):
                raise serializers.ValidationError("La talla de zapato debe ser un número")
            if n < 20 or n > 50:
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

        if instance.id_direccion_residencia:
            dir_obj = instance.id_direccion_residencia
            data['direccion'] = {
                'calle': dir_obj.calle,
                'ciudad': dir_obj.ciudad,
                'estado': dir_obj.estado,
                'referencia': dir_obj.referencia or '',
            }
        else:
            data['direccion'] = None

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
        Crea el alumno y, de forma atómica, la dirección (si viene), el representante
        (si no existe por cédula) y la relación pivot AlumnoRepresentante.
        """
        representante_data = validated_data.pop('representante', None)
        parentesco = validated_data.pop('parentesco', None)
        direccion_data = validated_data.pop('direccion', None)
        id_grupo = validated_data.pop('id_grupo', None)

        alumno = Alumnos.objects.create(**validated_data)

        if direccion_data:
            alumno.id_direccion_residencia = self._vincular_direccion(None, direccion_data)
            alumno.save()

        if id_grupo:
            self._vincular_grupo(alumno, id_grupo)

        if representante_data:
            self._vincular_representante(alumno, representante_data, parentesco)

        return alumno

    @transaction.atomic
    def update(self, instance, validated_data):
        representante_data = validated_data.pop('representante', None)
        parentesco = validated_data.pop('parentesco', None)
        direccion_data = validated_data.pop('direccion', None)
        id_grupo = validated_data.pop('id_grupo', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Si trae dirección: actualiza la existente o crea y vincula una nueva.
        if direccion_data:
            instance.id_direccion_residencia = self._vincular_direccion(
                instance.id_direccion_residencia, direccion_data
            )

        instance.save()

        if id_grupo:
            self._vincular_grupo(instance, id_grupo)

        if representante_data:
            self._vincular_representante(instance, representante_data, parentesco)

        return instance

    @staticmethod
    def _vincular_grupo(alumno, id_grupo):
        """Crea o actualiza la inscripción ACTIVA del alumno con el grupo indicado."""
        grupo = GruposAcademicos.objects.get(pk=id_grupo)
        inscripcion = Inscripciones.objects.filter(
            alumno=alumno, estado_inscripcion='Activa'
        ).first()
        if inscripcion:
            inscripcion.grupo = grupo
            inscripcion.save()
        else:
            Inscripciones.objects.create(
                alumno=alumno,
                grupo=grupo,
                fecha_inscripcion=timezone.now(),
                estado_inscripcion='Activa',
            )

    @staticmethod
    def _vincular_direccion(direccion_existente, direccion_data):
        """Crea o actualiza la dirección (core.Direcciones) y devuelve la instancia."""
        campos = {
            'calle': direccion_data['calle'],
            'ciudad': direccion_data['ciudad'],
            'estado': direccion_data['estado'],
            'referencia': direccion_data.get('referencia') or None,
        }
        if direccion_existente:
            for campo, valor in campos.items():
                setattr(direccion_existente, campo, valor)
            direccion_existente.save()
            return direccion_existente
        return Direcciones.objects.create(**campos)

    @staticmethod
    def _vincular_representante(alumno, representante_data, parentesco):
        """
        Vincula un alumno con su representante legal:
        - Si la cédula ya existe en representantes_legales, la reutiliza (get_or_create).
        - Si no existe, crea el registro.
        - Crea/actualiza la fila pivot en alumno_representante.

        NOTA: la tabla pivot tiene PK compuesta (id_alumno, id_representante) en la BD,
        pero el modelo Django declara solo id_alumno como PK; por eso se usan
        filter().update() / create() con WHERE completo en lugar de update_or_create()
        o save(), que harían un get()/UPDATE ambiguos con múltiples vínculos.
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

        valores = {
            'parentesco': parentesco or 'Sin especificar',
            'es_principal': True,
        }

        # 1) Si ya existe el vínculo (alumno, representante) -> actualizarlo.
        actualizados = AlumnoRepresentante.objects.filter(
            alumno=alumno, representante=representante
        ).update(**valores)

        # 2) Si no existe -> crearlo (create con force_insert, seguro con esta PK).
        if not actualizados:
            AlumnoRepresentante.objects.create(
                alumno=alumno, representante=representante, **valores
            )

        # 3) Un solo representante principal por alumno (el resto quedan como secundarios).
        AlumnoRepresentante.objects.filter(alumno=alumno).exclude(
            representante=representante
        ).update(es_principal=False)

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


# ============================================================================
# SERIALIZADORES PARA INSCRIPCIÓN CON REPRESENTANTE ANIDADO
# ============================================================================

class RepresentanteSerializer(serializers.Serializer):
    """
    Serializador para los datos básicos del tutor/representante legal.
    Se utiliza dentro del flujo de inscripción de alumnos.
    El campo 'cedula' no tiene validador único para permitir la reutilización
    de registros de representante (un tutor puede tener varios alumnos).
    """
    cedula = serializers.CharField(max_length=20, required=True, validators=[])
    nombre = serializers.CharField(max_length=150, required=True)
    apellido = serializers.CharField(max_length=150, required=True)
    telefono = serializers.CharField(max_length=20, required=True)
    correo = serializers.EmailField(required=False, allow_null=True, allow_blank=True)


class AlumnoInscripcionSerializer(serializers.Serializer):
    """
    Serializador para la inscripción de un alumno con su representante anidado.
    Crea en una transacción atómica:
      1. El representante (idempotente por cédula vía update_or_create).
      2. El registro del alumno.
      3. El vínculo AlumnoRepresentante (tabla pivote).
      4. La Inscripción académica formal en el grupo provisto.
    """
    # --- Datos del alumno ---
    primer_nombre = serializers.CharField(max_length=150, required=True)
    segundo_nombre = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    primer_apellido = serializers.CharField(max_length=150, required=True)
    segundo_apellido = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    tipo_documento_identidad = serializers.CharField(max_length=50, required=True)
    numero_documento_identidad = serializers.CharField(max_length=30, required=True)
    cedula_escolar = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    fecha_nacimiento = serializers.DateField(required=True)
    genero = serializers.CharField(max_length=50, required=True)
    lugar_nacimiento = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    nacionalidad = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    grupo_sanguineo = serializers.CharField(max_length=10, required=False, allow_blank=True, allow_null=True)
    alergico_a = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    peso_kg = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    talla_cm = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    fecha_inscripcion_inicial = serializers.DateField(required=False, allow_null=True)
    estatus_general = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)

    # --- Datos adicionales del alumno (formulario completo de inscripción) ---
    carnet_patria_codigo = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    carnet_patria_serial = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    numero_cuenta = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    tipo_cuenta = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    banco = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    entidad_federal_nacimiento = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    municipio_nacimiento = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    parroquia_nacimiento = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    condicion_fisica = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    apoyo_escolar = serializers.BooleanField(required=False, default=False)
    vacunas_completas = serializers.BooleanField(required=False, default=False)
    tratamiento_medico = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    talla_camisa = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    talla_pantalon = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    talla_zapato = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    estado_civil_padres = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    ingreso_familiar = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    profesion_madre = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    profesion_padre = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    tipo_vivienda = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    numero_hermanos = serializers.IntegerField(required=False, allow_null=True)
    numero_en_el_planter = serializers.IntegerField(required=False, allow_null=True)
    discapacidad = serializers.BooleanField(required=False, default=False)
    tipo_discapacidad = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    observaciones = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    # --- Dirección de residencia (anidada, opcional) ---
    direccion = DireccionAnidadaSerializer(
        required=False, allow_null=True,
        help_text='Dirección de residencia del alumno (se crea en core.Direcciones).',
    )

    # --- Representante anidado ---
    representante = RepresentanteSerializer(required=True)
    parentesco = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True,
                                       help_text='Parentesco del representante con el alumno.')

    # --- Datos de inscripción ---
    id_grupo = serializers.IntegerField(required=True)
    fecha_inscripcion = serializers.DateTimeField(required=False, allow_null=True)
    estado_inscripcion = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    monto_pago = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    referencia_bancaria = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)

    def create(self, validated_data):
        from apps.personal.models import RepresentantesLegales, AlumnoRepresentante

        representante_data = validated_data.pop('representante')
        parentesco = validated_data.pop('parentesco', 'Padre') or 'Padre'
        direccion_data = validated_data.pop('direccion', None)
        id_grupo = validated_data.pop('id_grupo')
        fecha_inscripcion = validated_data.pop('fecha_inscripcion', None) or timezone.now()
        estado_inscripcion = validated_data.pop('estado_inscripcion', 'Activa') or 'Activa'
        # Campos obligatorios de Alumnos no siempre enviados por el frontend:
        if not validated_data.get('fecha_inscripcion_inicial'):
            validated_data['fecha_inscripcion_inicial'] = timezone.now().date()
        if not validated_data.get('estatus_general'):
            validated_data['estatus_general'] = 'Activo'
        monto_pago = validated_data.pop('monto_pago', None)
        referencia_bancaria = validated_data.pop('referencia_bancaria', None)

        # Campos numéricos opcionales: cadena vacía => None (DRF rechaza '' en Decimal/Integer).
        for campo in ('peso_kg', 'talla_cm', 'ingreso_familiar', 'numero_hermanos', 'numero_en_el_planter'):
            if validated_data.get(campo) == '':
                validated_data[campo] = None

        try:
            with transaction.atomic():
                # 1) Resolver representante de forma idempotente por cédula.
                representante, _ = RepresentantesLegales.objects.update_or_create(
                    cedula=representante_data['cedula'],
                    defaults={
                        'primer_nombre': representante_data.get('nombre', ''),
                        'primer_apellido': representante_data.get('apellido', ''),
                        'telefono_principal': representante_data.get('telefono', ''),
                        'email': representante_data.get('correo') or None,
                    },
                )

                # 2) Crear el registro del alumno.
                alumno = Alumnos.objects.create(**validated_data)

                # 3) Vincular dirección de residencia (si se envió).
                if direccion_data:
                    direccion = Direcciones.objects.create(
                        calle=direccion_data.get('calle', ''),
                        ciudad=direccion_data.get('ciudad', ''),
                        estado=direccion_data.get('estado', ''),
                        referencia=direccion_data.get('referencia') or '',
                    )
                    alumno.id_direccion_residencia = direccion
                    alumno.save(update_fields=['id_direccion_residencia'])

                # 4) Vincular alumno y representante en la tabla pivote.
                AlumnoRepresentante.objects.create(
                    alumno=alumno,
                    representante=representante,
                    parentesco=parentesco,
                    es_principal=True,
                )

                # 5) Registrar la inscripción académica formal en el grupo provisto.
                grupo = GruposAcademicos.objects.get(pk=id_grupo)
                inscripcion = Inscripciones.objects.create(
                    alumno=alumno,
                    grupo=grupo,
                    fecha_inscripcion=fecha_inscripcion,
                    estado_inscripcion=estado_inscripcion,
                    monto_pago=monto_pago,
                    referencia_bancaria=referencia_bancaria,
                )

            return inscripcion

        except Exception as exc:
            logger.debug('Error en inscripción anidada con representante', exc_info=True)
            raise serializers.ValidationError(
                f'No se pudo completar la inscripción: {exc}'
            )


class DateTimeHastaFinDeDia(serializers.DateTimeField):
    """
    DateTimeField que, cuando recibe solo una fecha (YYYY-MM-DD), la
    interpreta como el final de ese día (23:59:59) en lugar de la
    medianoche.

    Se usa en 'fecha_fin' para que un periodo de inscripción incluya el
    día completo seleccionado en el formulario del frontend.
    """

    def to_internal_value(self, value):
        if isinstance(value, str) and len(value) == 10:
            value = f'{value}T23:59:59'
        return super().to_internal_value(value)


class PeriodoInscripcionSerializer(serializers.ModelSerializer):
    """
    Serializador de lectura/escritura para periodos de inscripción.

    Lectura: expone pk, nombre, calendario, estado del switch y token_acceso
    para que el panel administrativo pueda construir el formulario público
    y alternar el estado de cada periodo.

    Escritura: permite crear (POST) y editar (PATCH) nombre y fechas desde
    el frontend del personal administrativo. 'id' y 'token_acceso' son de
    solo lectura (el token se autogenera en el modelo).
    """

    # fecha_fin incluye el día completo cuando llega solo YYYY-MM-DD.
    fecha_fin = DateTimeHastaFinDeDia()

    class Meta:
        model = PeriodoInscripcion
        fields = [
            'id',
            'nombre',
            'fecha_inicio',
            'fecha_fin',
            'activo_manual',
            'token_acceso',
        ]
        read_only_fields = ['id', 'token_acceso']

    def validate(self, attrs):
        """La fecha de fin debe ser posterior a la de inicio (incluye PATCH parcial)."""
        fecha_inicio = attrs.get('fecha_inicio', getattr(self.instance, 'fecha_inicio', None))
        fecha_fin = attrs.get('fecha_fin', getattr(self.instance, 'fecha_fin', None))
        if fecha_inicio and fecha_fin and fecha_fin <= fecha_inicio:
            raise serializers.ValidationError(
                'La fecha de fin debe ser posterior a la fecha de inicio.'
            )
        return attrs


class NotaEstudianteInputSerializer(serializers.Serializer):
    """
    Nota individual de un estudiante dentro de un lote de carga masiva.

    Serializador plano (deliberadamente NO ModelSerializer) para minimizar el
    overhead de introspección de metadatos cuando se procesan secciones
    completas en una sola petición.

    JSON conceptual:
    {
      "id_alumno": 31,
      "nota_literal": "B",
      "informe_descriptivo": null
    }
    """

    id_alumno = serializers.IntegerField()
    nota_literal = serializers.CharField(
        max_length=1,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    informe_descriptivo = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )


class CargaMasivaCalificacionesSerializer(serializers.Serializer):
    """
    Lote de calificaciones de una sección (grupo académico) para un lapso.

    JSON conceptual:
    {
      "id_grupo_academico": 5,
      "calificaciones": [
        {"id_alumno": 31, "nota_literal": "B", "informe_descriptivo": null},
        {"id_alumno": 32, "nota_literal": null, "informe_descriptivo": "Avanza con entusiasmo"}
      ]
    }

    Reglas de negocio:
    - Atomicidad: si una sola nota del lote incumple las reglas pedagógicas
      (clean() de CalificacionLiteral), se revierte TODA la sección.
    - Idempotencia: update_or_create por (alumno, grupo, periodo); reenviar el
      formulario actualiza la nota preexistente sin error de duplicado.
    """

    id_grupo_academico = serializers.IntegerField()
    calificaciones = NotaEstudianteInputSerializer(many=True)

    def guardar_lote(self, periodo_objeto):
        """
        Persiste el lote de forma atómica e idempotente para el periodo dado.

        Retorna un resumen de la operación:
        {'id_grupo_academico', 'id_periodo', 'creadas', 'actualizadas', 'total'}
        """
        id_grupo_academico = self.validated_data['id_grupo_academico']
        items = self.validated_data['calificaciones']

        creadas = 0
        actualizadas = 0

        try:
            with transaction.atomic():
                for item in items:
                    nota_literal = (item.get('nota_literal') or '').strip() or None
                    informe_descriptivo = (item.get('informe_descriptivo') or '').strip() or None

                    _, creado = CalificacionLiteral.objects.update_or_create(
                        alumno_id=item['id_alumno'],
                        grupo_id=id_grupo_academico,
                        periodo=periodo_objeto,
                        defaults={
                            'nota_literal': nota_literal,
                            'informe_descriptivo': informe_descriptivo,
                        },
                    )
                    if creado:
                        creadas += 1
                    else:
                        actualizadas += 1
        except ValidationError:
            # Auditoría: el traceback queda registrado y la excepción se
            # propaga para que la vista responda al cliente. Al capturar
            # FUERA del bloque atomic, el rollback de la sección completa
            # (incluidas las notas ya escritas del lote) ya se ejecutó.
            logger.debug(
                'Rollback del lote de calificaciones del grupo %s (lapso %s)',
                id_grupo_academico, getattr(periodo_objeto, 'pk', None), exc_info=True,
            )
            raise
        except IntegrityError:
            logger.debug(
                'Error de integridad en el lote de calificaciones del grupo %s (lapso %s)',
                id_grupo_academico, getattr(periodo_objeto, 'pk', None), exc_info=True,
            )
            raise

        return {
            'id_grupo_academico': id_grupo_academico,
            'id_periodo': periodo_objeto.pk,
            'creadas': creadas,
            'actualizadas': actualizadas,
            'total': len(items),
        }


class PeriodoCalificacionSerializer(serializers.ModelSerializer):
    """
    Configuración administrativa de un lapso de calificación (Diciembre,
    Abril o Julio).

    El panel puede modificar 'fecha_limite' y alternar 'activo_manual';
    'token_acceso' es de solo lectura porque se autogenera en el modelo.
    """

    class Meta:
        model = PeriodoCalificacion
        fields = ['id', 'numero_periodo', 'fecha_limite', 'activo_manual', 'token_acceso']
        read_only_fields = ['id', 'token_acceso']
