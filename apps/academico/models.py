import hashlib
import secrets

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from django.db import models
from django.utils import timezone


def generar_nombre_unico_archivo(instance, filename):
    # Se usa MD5 exclusivamente para acortar el nombre (no para fines criptográficos)
    hash_txt = hashlib.md5(filename.encode('utf-8'), usedforsecurity=False).hexdigest()
    return f"tareas/{hash_txt}_{filename}"


class Alumnos(models.Model):
    id_alumno = models.AutoField(primary_key=True, db_column='id_alumno')
    id_usuario = models.ForeignKey(
        'core.Usuarios',
        on_delete=models.SET_NULL,
        db_column='id_usuario',
        blank=True,
        null=True
    )
    id_direccion_residencia = models.ForeignKey(
        'core.Direcciones',
        on_delete=models.SET_NULL,
        db_column='id_direccion_residencia',
        blank=True,
        null=True
    )
    # Profesor encargado (Docente Guía) asignado directamente al alumno.
    id_profesor_encargado = models.ForeignKey(
        'personal.Profesores',
        on_delete=models.SET_NULL,
        db_column='id_profesor_encargado',
        blank=True,
        null=True,
        related_name='alumnos_asignados'
    )
    primer_nombre = models.CharField(max_length=150, db_column='primer_nombre')
    segundo_nombre = models.CharField(max_length=150, blank=True, null=True, db_column='segundo_nombre')
    primer_apellido = models.CharField(max_length=150, db_column='primer_apellido')
    segundo_apellido = models.CharField(max_length=150, blank=True, null=True, db_column='segundo_apellido')
    tipo_documento_identidad = models.CharField(max_length=50, db_column='tipo_documento_identidad')
    numero_documento_identidad = models.CharField(max_length=30, unique=True, db_column='numero_documento_identidad')
    cedula_escolar = models.CharField(max_length=30, blank=True, null=True, unique=True, db_column='cedula_escolar')
    fecha_nacimiento = models.DateField(db_column='fecha_nacimiento')
    genero = models.CharField(max_length=50, db_column='genero')
    lugar_nacimiento = models.CharField(max_length=255, blank=True, null=True, db_column='lugar_nacimiento')
    nacionalidad = models.CharField(max_length=100, blank=True, null=True, db_column='nacionalidad')
    carnet_patria_codigo = models.CharField(max_length=50, blank=True, null=True, db_column='carnet_patria_codigo')
    carnet_patria_serial = models.CharField(max_length=50, blank=True, null=True, db_column='carnet_patria_serial')
    numero_cuenta = models.CharField(max_length=30, blank=True, null=True, db_column='numero_cuenta')
    tipo_cuenta = models.CharField(max_length=20, blank=True, null=True, db_column='tipo_cuenta')
    banco = models.CharField(max_length=100, blank=True, null=True, db_column='banco')
    entidad_federal_nacimiento = models.CharField(max_length=100, blank=True, null=True, db_column='entidad_federal_nacimiento')
    municipio_nacimiento = models.CharField(max_length=100, blank=True, null=True, db_column='municipio_nacimiento')
    parroquia_nacimiento = models.CharField(max_length=100, blank=True, null=True, db_column='parroquia_nacimiento')
    condicion_fisica = models.TextField(blank=True, null=True, db_column='condicion_fisica')
    grupo_sanguineo = models.CharField(max_length=10, blank=True, null=True, db_column='grupo_sanguineo')
    apoyo_escolar = models.BooleanField(default=False, db_column='apoyo_escolar')
    vacunas_completas = models.BooleanField(default=False, db_column='vacunas_completas')
    alergico_a = models.TextField(blank=True, null=True, db_column='alergico_a')
    tratamiento_medico = models.TextField(blank=True, null=True, db_column='tratamiento_medico')
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='peso_kg')
    talla_cm = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='talla_cm')
    talla_camisa = models.CharField(max_length=20, blank=True, null=True, db_column='talla_camisa')
    talla_pantalon = models.CharField(max_length=20, blank=True, null=True, db_column='talla_pantalon')
    talla_zapato = models.CharField(max_length=20, blank=True, null=True, db_column='talla_zapato')
    estado_civil_padres = models.CharField(max_length=50, blank=True, null=True, db_column='estado_civil_padres')
    ingreso_familiar = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, db_column='ingreso_familiar')
    profesion_madre = models.CharField(max_length=150, blank=True, null=True, db_column='profesion_madre')
    profesion_padre = models.CharField(max_length=150, blank=True, null=True, db_column='profesion_padre')
    tipo_vivienda = models.CharField(max_length=50, blank=True, null=True, db_column='tipo_vivienda')
    numero_hermanos = models.IntegerField(blank=True, null=True, db_column='numero_hermanos')
    numero_en_el_planter = models.IntegerField(blank=True, null=True, db_column='numero_en_el_planter')
    discapacidad = models.BooleanField(default=False, db_column='discapacidad')
    tipo_discapacidad = models.TextField(blank=True, null=True, db_column='tipo_discapacidad')
    observaciones = models.TextField(blank=True, null=True, db_column='observaciones')
    fecha_inscripcion_inicial = models.DateField(db_column='fecha_inscripcion_inicial')
    estatus_general = models.CharField(max_length=50, db_column='estatus_general')

    class Meta:
        managed = False
        db_table = 'alumnos'
        verbose_name = 'Alumno'
        verbose_name_plural = 'Alumnos'

    def __str__(self):
        return f"{self.primer_nombre} {self.primer_apellido} - C.E.: {self.cedula_escolar}"


class GruposAcademicos(models.Model):
    id_grupo = models.AutoField(primary_key=True, db_column='id_grupo')
    periodo = models.ForeignKey('core.PeriodosAcademicos', on_delete=models.PROTECT, db_column='id_periodo')
    nivel = models.ForeignKey('core.NivelesEducativos', on_delete=models.PROTECT, db_column='id_nivel', blank=True, null=True)
    grado = models.ForeignKey('core.GradosAcademicos', on_delete=models.PROTECT, db_column='id_grado')
    seccion = models.ForeignKey('core.Secciones', on_delete=models.PROTECT, db_column='id_seccion')
    turno = models.ForeignKey('core.Turnos', on_delete=models.PROTECT, db_column='id_turno')
    profesor_director = models.ForeignKey('personal.Profesores', on_delete=models.SET_NULL, db_column='id_profesor_principal', blank=True, null=True)
    cupo_maximo = models.IntegerField(default=30, db_column='cupo_maximo')

    class Meta:
        managed = False
        db_table = 'grupos_academicos'
        verbose_name = 'Grupo Académico'
        verbose_name_plural = 'Grupos Académicos'

    def __str__(self):
        return f"{self.grado.nombre_grado} '{self.seccion.nombre_seccion}' - {self.periodo.nombre_periodo}"


class Inscripciones(models.Model):
    ESTADO_CHOICES = [
        ('Activa', 'Activa'),
        ('Retirado', 'Retirado'),
        ('Graduado', 'Graduado'),
    ]

    id_inscripcion = models.AutoField(primary_key=True, db_column='id_inscripcion')
    # CASCADE alineado con la FK legacy fk_inscripcion_id_alumno (DELETE_RULE=CASCADE):
    # eliminar un alumno borra su historial (inscripciones -> calificaciones, asistencias).
    alumno = models.ForeignKey('Alumnos', on_delete=models.CASCADE, db_column='id_alumno', related_name='inscripciones')
    grupo = models.ForeignKey(GruposAcademicos, on_delete=models.PROTECT, db_column='id_grupo')
    fecha_inscripcion = models.DateTimeField(blank=True, null=True, db_column='fecha_inscripcion')
    estado_inscripcion = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='Activa', db_column='estado_inscripcion')
    monto_pago = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, db_column='monto_pago')
    referencia_bancaria = models.CharField(max_length=100, blank=True, null=True, db_column='referencia_bancaria')

    class Meta:
        managed = False
        db_table = 'inscripciones'
        verbose_name = 'Inscripción'
        verbose_name_plural = 'Inscripciones'

    def __str__(self):
        return f"Inscripción #{self.id_inscripcion} - {self.alumno.primer_nombre} {self.alumno.primer_apellido}"


class Calificaciones(models.Model):
    id_calificacion = models.AutoField(primary_key=True, db_column='id_calificacion')
    inscripcion = models.ForeignKey(Inscripciones, on_delete=models.CASCADE, db_column='id_inscripcion')
    profesor = models.ForeignKey('personal.Profesores', on_delete=models.SET_NULL, db_column='id_profesor', blank=True, null=True)
    calificacion = models.CharField(max_length=50, blank=True, null=True, db_column='calificacion')
    fecha_registro = models.DateTimeField(blank=True, null=True, db_column='fecha_registro')

    class Meta:
        managed = False
        db_table = 'calificaciones'
        verbose_name = 'Calificación'
        verbose_name_plural = 'Calificaciones'

    def __str__(self):
        return f"Calificación: {self.calificacion} - Alumno: {self.inscripcion.alumno.primer_nombre} {self.inscripcion.alumno.primer_apellido}"

class Asistencias(models.Model):
    ESTADO_CHOICES = [
        ('P', 'Presente'),
        ('A', 'Ausente'),
        ('J', 'Justificado'),
    ]

    id_asistencia = models.AutoField(primary_key=True, db_column='id_asistencia')
    fecha = models.DateField(db_column='fecha')
    alumno = models.ForeignKey(Alumnos, on_delete=models.CASCADE, db_column='id_alumno')
    grupo = models.ForeignKey(GruposAcademicos, on_delete=models.CASCADE, db_column='id_grupo')
    estado = models.CharField(max_length=1, choices=ESTADO_CHOICES, db_column='estado')
    observaciones = models.TextField(blank=True, null=True, db_column='observaciones')
    profesor_registro = models.ForeignKey('personal.Profesores', on_delete=models.SET_NULL, db_column='id_profesor_registro', blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True, db_column='fecha_registro')

    class Meta:
        managed = False
        db_table = 'asistencias'
        verbose_name = 'Asistencia'
        verbose_name_plural = 'Asistencias'
        unique_together = [('fecha', 'alumno', 'grupo')]

    def __str__(self):
        return f"{self.alumno.primer_nombre} {self.alumno.primer_apellido} - {self.fecha} - {self.get_estado_display()}"


class PeriodoInscripcion(models.Model):
    """
    Control dinámico del periodo de inscripciones externas.

    La tabla es administrada por Django (managed=True por defecto) y se
    materializa físicamente en MariaDB como 'periodo_inscripcion'.

    Reglas de negocio:
    - 'activo_manual' tiene prioridad absoluta sobre el calendario.
    - 'token_acceso' se autogenera con secrets.token_urlsafe(32) si viene vacío.
    """

    nombre = models.CharField(
        max_length=100,
        default="Inscripciones Año Escolar",
        db_column='nombre',
    )
    fecha_inicio = models.DateTimeField(db_column='fecha_inicio')
    fecha_fin = models.DateTimeField(db_column='fecha_fin')
    activo_manual = models.BooleanField(
        default=True,
        db_column='activo_manual',
        help_text="Switch/botón de la interfaz. Prioridad absoluta sobre el calendario.",
    )
    token_acceso = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        db_column='token_acceso',
        help_text="Token alfanumérico seguro para URL de acceso público.",
    )

    class Meta:
        db_table = 'periodo_inscripcion'
        verbose_name = 'Periodo de Inscripción'
        verbose_name_plural = 'Periodos de Inscripción'

    def save(self, *args, **kwargs):
        if not self.token_acceso:
            self.token_acceso = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def esta_disponible(self):
        """
        Retorna True si el periodo está abierto para inscripciones.

        Regla estricta:
        1. Si activo_manual es False -> retorna False inmediatamente
           (prioridad absoluta del switch manual).
        2. Si activo_manual es True -> valida que now() esté entre
           fecha_inicio y fecha_fin.
        """
        if not self.activo_manual:
            return False

        ahora = timezone.now()
        return self.fecha_inicio <= ahora <= self.fecha_fin

    def __str__(self):
        return f"PeriodoInscripcion #{self.pk} - {self.nombre}"


class PeriodoCalificacion(models.Model):
    """
    Lapso de calificaciones del Sistema de Boletas Consolidadas de Tres Lapsos.

    La tabla es administrada por Django (managed=True por defecto) y se
    materializa físicamente en MariaDB como 'periodo_calificacion'.

    Reglas de negocio:
    - 'numero_periodo' es único: 1=Diciembre, 2=Abril, 3=Julio.
    - 'token_acceso' se autogenera con secrets.token_urlsafe(32) si viene vacío
      y alimenta la URL de carga de notas de los docentes.
    """

    NUMERO_PERIODO_CHOICES = [
        (1, 'Diciembre'),
        (2, 'Abril'),
        (3, 'Julio'),
    ]

    numero_periodo = models.IntegerField(
        choices=NUMERO_PERIODO_CHOICES,
        unique=True,
        db_column='numero_periodo',
        help_text="Lapso del año escolar: 1=Diciembre, 2=Abril, 3=Julio.",
    )
    fecha_limite = models.DateTimeField(
        db_column='fecha_limite',
        help_text="Fecha y hora límite para que los profesores carguen las notas.",
    )
    activo_manual = models.BooleanField(
        default=True,
        db_column='activo_manual',
        help_text="Switch de la interfaz de administración.",
    )
    token_acceso = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        db_column='token_acceso',
        help_text="Token seguro para la URL de acceso de los docentes.",
    )

    class Meta:
        db_table = 'periodo_calificacion'
        verbose_name = 'Periodo de Calificación'
        verbose_name_plural = 'Periodos de Calificación'

    def save(self, *args, **kwargs):
        if not self.token_acceso:
            self.token_acceso = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def esta_abierto(self):
        """
        Indica si el lapso admite la carga de notas por parte de los docentes.

        Regla estricta:
        1. Si activo_manual es False (switch de la interfaz administrativa
           apagado) → retorna False inmediatamente.
        2. Si now() superó la fecha_limite → retorna False.
        """
        if not self.activo_manual:
            return False
        return timezone.now() <= self.fecha_limite

    def __str__(self):
        return f"PeriodoCalificacion #{self.pk} - {self.get_numero_periodo_display()}"


class CalificacionLiteral(models.Model):
    """
    Nota literal (A-E) o informe descriptivo por alumno, grupo y lapso.

    Reglas pedagógicas (validadas en clean() y ejecutadas siempre desde save()
    mediante self.full_clean()):
    - Inicial/Preescolar: se prohíbe la 'nota_literal' y el
      'informe_descriptivo' es obligatorio.
    - Primaria (1ro a 6to grado): la 'nota_literal' (A-E) es obligatoria y el
      'informe_descriptivo' es opcional.
    - La 'nota_literal' se normaliza a mayúscula antes de persistir.
    """

    alumno = models.ForeignKey(Alumnos, on_delete=models.CASCADE, db_column='id_alumno')
    grupo = models.ForeignKey(GruposAcademicos, on_delete=models.CASCADE, db_column='id_grupo_academico')
    periodo = models.ForeignKey(PeriodoCalificacion, on_delete=models.PROTECT, db_column='id_periodo')
    nota_literal = models.CharField(
        max_length=1,
        blank=True,
        null=True,
        db_column='nota_literal',
        validators=[
            RegexValidator(
                regex=r'^[A-Ea-e]$',
                message="La nota literal debe ser una letra de la A a la E (mayúscula o minúscula).",
            ),
        ],
        help_text="Literal A-E (Primaria). Debe ir vacío en Inicial/Preescolar.",
    )
    informe_descriptivo = models.TextField(
        blank=True,
        null=True,
        db_column='informe_descriptivo',
        help_text="Relato del desarrollo del estudiante; obligatorio en Inicial/Preescolar.",
    )
    fecha_registro = models.DateTimeField(auto_now_add=True, db_column='fecha_registro')

    class Meta:
        db_table = 'calificacion_literal'
        verbose_name = 'Calificación Literal'
        verbose_name_plural = 'Calificaciones Literales'
        unique_together = ('alumno', 'grupo', 'periodo')

    def clean(self):
        super().clean()

        # Normaliza la nota a mayúscula antes de validar las reglas de negocio
        # (full_clean() invoca clean_fields() antes que clean(), por eso el
        # RegexValidator acepta A-E en ambos casos).
        if self.nota_literal:
            self.nota_literal = self.nota_literal.strip().upper() or None

        # Determina el nivel pedagógico del grupo (nivel puede ser NULL en la
        # tabla legacy, por eso se respalda la detección con el nombre del grado).
        nivel_nombre = ''
        grado_nombre = ''
        if self.grupo_id is not None:
            try:
                grupo = self.grupo
            except GruposAcademicos.DoesNotExist:
                grupo = None
            if grupo is not None:
                nivel_nombre = (grupo.nivel.nombre_nivel or '') if grupo.nivel_id else ''
                grado_nombre = (grupo.grado.nombre_grado or '') if grupo.grado_id else ''

        nombre_nivel = nivel_nombre.upper()
        nombre_grado = grado_nombre.upper()

        es_inicial = (
            'INICIAL' in nombre_nivel
            or 'PREESCOLAR' in nombre_nivel
            or 'INICIAL' in nombre_grado
        )
        grados_primaria = (
            'PRIMER GRADO', 'SEGUNDO GRADO', 'TERCER GRADO',
            'CUARTO GRADO', 'QUINTO GRADO', 'SEXTO GRADO',
        )
        es_primaria = 'PRIMARIA' in nombre_nivel or any(g in nombre_grado for g in grados_primaria)

        if es_inicial:
            errores = {}
            if self.nota_literal:
                errores['nota_literal'] = (
                    'En Inicial/Preescolar no se asigna nota literal (A-E); '
                    'registre únicamente el informe descriptivo.'
                )
            if not self.informe_descriptivo or not self.informe_descriptivo.strip():
                errores['informe_descriptivo'] = (
                    'En Inicial/Preescolar el informe descriptivo es obligatorio.'
                )
            if errores:
                raise ValidationError(errores)
        elif es_primaria:
            if not self.nota_literal:
                raise ValidationError({
                    'nota_literal': (
                        'En Primaria (1ro a 6to grado) la nota literal (A-E) es obligatoria.'
                    ),
                })

    def save(self, *args, **kwargs):
        # La nota se persiste siempre en mayúscula (A-E).
        if self.nota_literal is not None:
            self.nota_literal = self.nota_literal.strip().upper() or None
        # fecha_registro se setea antes de validar para que full_clean() no lo
        # vea vacío (auto_now_add lo fijará igual en pre_save).
        if self.fecha_registro is None:
            self.fecha_registro = timezone.now()
        # Las reglas pedagógicas y los validadores de campo se ejecutan SIEMPRE.
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.nota_literal:
            return (
                f"CalificaciónLiteral {self.nota_literal} - "
                f"{self.alumno.primer_nombre} {self.alumno.primer_apellido} "
                f"(Periodo {self.periodo.numero_periodo})"
            )
        return (
            f"CalificaciónLiteral (informe) - "
            f"{self.alumno.primer_nombre} {self.alumno.primer_apellido} "
            f"(Periodo {self.periodo.numero_periodo})"
        )
