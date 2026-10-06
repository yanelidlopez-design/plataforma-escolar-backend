"""
Modelos de Django mapeados desde la estructura SQL plataforma_escolar_v7.sql
Plataforma Escolar Backend
"""

from django.db import models


class ConfiguracionPlantel(models.Model):
    id_config = models.SmallAutoField(primary_key=True, db_column='id_config')
    nombre_plantel = models.CharField(max_length=255, db_column='nombre_plantel')
    codigo_estadistico = models.CharField(max_length=50, unique=True, db_column='codigo_estadistico')
    codigo_plantel = models.CharField(max_length=50, unique=True, db_column='codigo_plantel')
    nombre_director = models.CharField(max_length=255, db_column='nombre_director')
    cedula_director = models.CharField(max_length=30, null=True, blank=True, db_column='cedula_director')

    class Meta:
        db_table = 'configuracion_plantel'
        verbose_name = 'Configuración del Plantel'
        verbose_name_plural = 'Configuraciones de Planteles'

    def __str__(self):
        return f"{self.nombre_plantel} ({self.codigo_plantel})"


class PeriodoAcademico(models.Model):
    id_periodo = models.AutoField(primary_key=True, db_column='id_periodo')
    codigo_periodo = models.CharField(max_length=50, unique=True, db_column='codigo_periodo')
    nombre_periodo = models.CharField(max_length=100, db_column='nombre_periodo')
    fecha_inicio = models.DateField(db_column='fecha_inicio')
    fecha_fin = models.DateField(db_column='fecha_fin')
    activo = models.BooleanField(default=True, db_column='activo')

    class Meta:
        db_table = 'periodos_academicos'
        verbose_name = 'Período Académico'
        verbose_name_plural = 'Períodos Académicos'

    def __str__(self):
        return self.nombre_periodo


class NivelEducativo(models.Model):
    id_nivel = models.SmallAutoField(primary_key=True, db_column='id_nivel')
    nombre_nivel = models.CharField(max_length=100, unique=True, db_column='nombre_nivel')

    class Meta:
        db_table = 'niveles_educativos'
        verbose_name = 'Nivel Educativo'
        verbose_name_plural = 'Niveles Educativos'

    def __str__(self):
        return self.nombre_nivel


class Turno(models.Model):
    id_turno = models.SmallAutoField(primary_key=True, db_column='id_turno')
    nombre_turno = models.CharField(max_length=100, unique=True, db_column='nombre_turno')

    class Meta:
        db_table = 'turnos'
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'

    def __str__(self):
        return self.nombre_turno


class GradoAcademico(models.Model):
    id_grado = models.SmallAutoField(primary_key=True, db_column='id_grado')
    id_nivel = models.ForeignKey(
        NivelEducativo,
        on_delete=models.RESTRICT,
        db_column='id_nivel',
        related_name='grados'
    )
    nombre_grado = models.CharField(max_length=50, db_column='nombre_grado')
    orden = models.IntegerField(null=True, blank=True, db_column='orden')

    class Meta:
        db_table = 'grados_academicos'
        unique_together = (('id_nivel', 'nombre_grado'),)
        verbose_name = 'Grado Académico'
        verbose_name_plural = 'Grados Académicos'

    def __str__(self):
        return f"{self.nombre_grado} - {self.id_nivel.nombre_nivel}"


class Seccion(models.Model):
    id_seccion = models.SmallAutoField(primary_key=True, db_column='id_seccion')
    nombre_seccion = models.CharField(max_length=50, unique=True, db_column='nombre_seccion')

    class Meta:
        db_table = 'secciones'
        verbose_name = 'Sección'
        verbose_name_plural = 'Secciones'

    def __str__(self):
        return f"Sección {self.nombre_seccion}"


class Direccion(models.Model):
    id_direccion = models.AutoField(primary_key=True, db_column='id_direccion')
    calle = models.CharField(max_length=255, db_column='calle')
    ciudad = models.CharField(max_length=100, db_column='ciudad')
    estado = models.CharField(max_length=100, db_column='estado')
    referencia = models.TextField(null=True, blank=True, db_column='referencia')

    class Meta:
        db_table = 'direcciones'
        verbose_name = 'Dirección'
        verbose_name_plural = 'Direcciones'

    def __str__(self):
        return f"{self.calle}, {self.ciudad} - {self.estado}"


class Usuario(models.Model):
    ROL_CHOICES = (
        ('ADMINISTRADOR', 'Administrador'),
        ('PROFESOR', 'Profesor'),
        ('DIRECTIVO', 'Directivo'),
        ('ESTUDIANTE', 'Estudiante'),
    )

    id_usuario = models.AutoField(primary_key=True, db_column='id_usuario')
    nombre_usuario = models.CharField(max_length=100, unique=True, db_column='nombre_usuario')
    clave_hash = models.CharField(max_length=255, db_column='clave_hash')
    email = models.EmailField(max_length=150, unique=True, db_column='email')
    rol = models.CharField(max_length=50, choices=ROL_CHOICES, db_column='rol')
    activo = models.BooleanField(default=True, db_column='activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_column='fecha_creacion')

    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.nombre_usuario} ({self.rol})"


class Profesor(models.Model):
    id_profesor = models.AutoField(primary_key=True, db_column='id_profesor')
    id_usuario = models.OneToOneField(
        Usuario,
        on_delete=models.RESTRICT,
        db_column='id_usuario',
        related_name='profesor_profile'
    )
    nombres = models.CharField(max_length=150, db_column='nombres')
    apellidos = models.CharField(max_length=150, db_column='apellidos')
    cedula = models.CharField(max_length=30, unique=True, db_column='cedula')
    especialidad = models.CharField(max_length=150, null=True, blank=True, db_column='especialidad')

    class Meta:
        db_table = 'profesores'
        verbose_name = 'Profesor'
        verbose_name_plural = 'Profesores'

    def __str__(self):
        return f"Prof. {self.nombres} {self.apellidos} - C.I. {self.cedula}"


class Alumno(models.Model):
    GENERO_CHOICES = (
        ('Masculino', 'Masculino'),
        ('Femenino', 'Femenino'),
        ('Otro', 'Otro'),
    )

    ESTATUS_CHOICES = (
        ('Activo', 'Activo'),
        ('Retirado', 'Retirado'),
        ('Egresado', 'Egresado'),
        ('Otro', 'Otro'),
    )

    id_alumno = models.AutoField(primary_key=True, db_column='id_alumno')
    id_usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='id_usuario',
        related_name='alumno_profile'
    )
    id_direccion_residencia = models.ForeignKey(
        Direccion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_direccion_residencia',
        related_name='alumnos'
    )

    # Identificación Personal
    primer_nombre = models.CharField(max_length=150, db_column='primer_nombre')
    segundo_nombre = models.CharField(max_length=150, null=True, blank=True, db_column='segundo_nombre')
    primer_apellido = models.CharField(max_length=150, db_column='primer_apellido')
    segundo_apellido = models.CharField(max_length=150, null=True, blank=True, db_column='segundo_apellido')
    tipo_documento_identidad = models.CharField(max_length=50, db_column='tipo_documento_identidad')
    numero_documento_identidad = models.CharField(max_length=30, unique=True, db_column='numero_documento_identidad')
    cedula_escolar = models.CharField(max_length=30, unique=True, null=True, blank=True, db_column='cedula_escolar')
    fecha_nacimiento = models.DateField(db_column='fecha_nacimiento')
    genero = models.CharField(max_length=20, choices=GENERO_CHOICES, db_column='genero')

    # Lugar de Nacimiento
    lugar_nacimiento = models.CharField(max_length=255, null=True, blank=True, db_column='lugar_nacimiento')
    nacionalidad = models.CharField(max_length=100, null=True, blank=True, db_column='nacionalidad')
    entidad_federal_nacimiento = models.CharField(max_length=100, null=True, blank=True, db_column='entidad_federal_nacimiento')
    municipio_nacimiento = models.CharField(max_length=100, null=True, blank=True, db_column='municipio_nacimiento')
    parroquia_nacimiento = models.CharField(max_length=100, null=True, blank=True, db_column='parroquia_nacimiento')

    # Datos Antropométricos y Salud
    condicion_fisica = models.TextField(null=True, blank=True, db_column='condicion_fisica')
    grupo_sanguineo = models.CharField(max_length=10, null=True, blank=True, db_column='grupo_sanguineo')
    apoyo_escolar = models.BooleanField(default=False, db_column='apoyo_escolar')
    vacunas_completas = models.BooleanField(default=False, db_column='vacunas_completas')
    alergico_a = models.TextField(null=True, blank=True, db_column='alergico_a')
    tratamiento_medico = models.TextField(null=True, blank=True, db_column='tratamiento_medico')
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, db_column='peso_kg')
    talla_cm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, db_column='talla_cm')
    talla_camisa = models.CharField(max_length=20, null=True, blank=True, db_column='talla_camisa')
    talla_pantalon = models.CharField(max_length=20, null=True, blank=True, db_column='talla_pantalon')
    talla_zapato = models.CharField(max_length=20, null=True, blank=True, db_column='talla_zapato')

    # Entorno Socio-Económico
    estado_civil_padres = models.CharField(max_length=50, null=True, blank=True, db_column='estado_civil_padres')
    ingreso_familiar = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, db_column='ingreso_familiar')
    profesion_madre = models.CharField(max_length=150, null=True, blank=True, db_column='profesion_madre')
    profesion_padre = models.CharField(max_length=150, null=True, blank=True, db_column='profesion_padre')
    tipo_vivienda = models.CharField(max_length=50, null=True, blank=True, db_column='tipo_vivienda')
    numero_hermanos = models.IntegerField(null=True, blank=True, db_column='numero_hermanos')
    numero_en_el_planter = models.IntegerField(null=True, blank=True, db_column='numero_en_el_planter')
    discapacidad = models.BooleanField(default=False, db_column='discapacidad')
    tipo_discapacidad = models.TextField(null=True, blank=True, db_column='tipo_discapacidad')
    observaciones = models.TextField(null=True, blank=True, db_column='observaciones')

    # Estado Académico
    fecha_inscripcion_inicial = models.DateField(db_column='fecha_inscripcion_inicial')
    estatus_general = models.CharField(
        max_length=20,
        choices=ESTATUS_CHOICES,
        default='Activo',
        db_column='estatus_general'
    )

    class Meta:
        db_table = 'alumnos'
        verbose_name = 'Alumno'
        verbose_name_plural = 'Alumnos'

    def __str__(self):
        return f"{self.primer_apellido} {self.primer_nombre} ({self.numero_documento_identidad})"


class RepresentanteLegal(models.Model):
    id_representante = models.AutoField(primary_key=True, db_column='id_representante')
    id_direccion_residencia = models.ForeignKey(
        Direccion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_direccion_residencia',
        related_name='representantes'
    )
    nombres = models.CharField(max_length=150, db_column='nombres')
    apellidos = models.CharField(max_length=150, db_column='apellidos')
    cedula = models.CharField(max_length=30, unique=True, db_column='cedula')
    carnet_patria = models.CharField(max_length=50, null=True, blank=True, db_column='carnet_patria')
    telefono = models.CharField(max_length=25, db_column='telefono')
    email = models.EmailField(max_length=150, null=True, blank=True, db_column='email')
    ocupacion = models.CharField(max_length=100, null=True, blank=True, db_column='ocupacion')

    class Meta:
        db_table = 'representantes_legales'
        verbose_name = 'Representante Legal'
        verbose_name_plural = 'Representantes Legales'

    def __str__(self):
        return f"{self.nombres} {self.apellidos} - C.I. {self.cedula}"


class AlumnoRepresentante(models.Model):
    id_alumno = models.ForeignKey(
        Alumno,
        on_delete=models.CASCADE,
        db_column='id_alumno',
        related_name='representante_rel'
    )
    id_representante = models.ForeignKey(
        RepresentanteLegal,
        on_delete=models.RESTRICT,
        db_column='id_representante',
        related_name='alumno_rel'
    )
    parentesco = models.CharField(max_length=50, db_column='parentesco')
    es_principal = models.BooleanField(default=False, db_column='es_principal')

    class Meta:
        db_table = 'alumno_representante'
        unique_together = (('id_alumno', 'id_representante'),)
        verbose_name = 'Relación Alumno - Representante'
        verbose_name_plural = 'Relaciones Alumno - Representantes'


class GrupoAcademico(models.Model):
    id_grupo = models.AutoField(primary_key=True, db_column='id_grupo')
    id_periodo = models.ForeignKey(
        PeriodoAcademico,
        on_delete=models.RESTRICT,
        db_column='id_periodo',
        related_name='grupos'
    )
    id_nivel = models.ForeignKey(
        NivelEducativo,
        on_delete=models.RESTRICT,
        db_column='id_nivel',
        related_name='grupos'
    )
    id_grado = models.ForeignKey(
        GradoAcademico,
        on_delete=models.RESTRICT,
        db_column='id_grado',
        related_name='grupos'
    )
    id_seccion = models.ForeignKey(
        Seccion,
        on_delete=models.RESTRICT,
        db_column='id_seccion',
        related_name='grupos'
    )
    id_turno = models.ForeignKey(
        Turno,
        on_delete=models.RESTRICT,
        db_column='id_turno',
        related_name='grupos'
    )
    id_profesor_principal = models.ForeignKey(
        Profesor,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column='id_profesor_principal',
        related_name='grupos_asignados'
    )
    cupo_maximo = models.PositiveSmallIntegerField(default=30, db_column='cupo_maximo')

    class Meta:
        db_table = 'grupos_academicos'
        unique_together = (('id_periodo', 'id_nivel', 'id_grado', 'id_seccion', 'id_turno'),)
        verbose_name = 'Grupo Académico'
        verbose_name_plural = 'Grupos Académicos'

    def __str__(self):
        return f"{self.id_grado.nombre_grado} '{self.id_seccion.nombre_seccion}' - {self.id_periodo.nombre_periodo}"


class Inscripcion(models.Model):
    ESTADO_CHOICES = (
        ('Activa', 'Activa'),
        ('Retirado', 'Retirado'),
        ('Egresado', 'Egresado'),
    )

    id_inscripcion = models.AutoField(primary_key=True, db_column='id_inscripcion')
    id_alumno = models.ForeignKey(
        Alumno,
        on_delete=models.CASCADE,
        db_column='id_alumno',
        related_name='inscripciones'
    )
    id_grupo = models.ForeignKey(
        GrupoAcademico,
        on_delete=models.RESTRICT,
        db_column='id_grupo',
        related_name='inscripciones'
    )
    fecha_inscripcion = models.DateTimeField(auto_now_add=True, db_column='fecha_inscripcion')
    estado_inscripcion = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='Activa',
        db_column='estado_inscripcion'
    )
    monto_pago = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, db_column='monto_pago')
    referencia_bancaria = models.CharField(max_length=100, null=True, blank=True, db_column='referencia_bancaria')

    class Meta:
        db_table = 'inscripciones'
        unique_together = (('id_alumno', 'id_grupo'),)
        verbose_name = 'Inscripción'
        verbose_name_plural = 'Inscripciones'

    def __str__(self):
        return f"Inscripción #{self.id_inscripcion} - {self.id_alumno}"


class Calificacion(models.Model):
    CALIFICACION_CHOICES = (
        ('A', 'A - Excelente'),
        ('B', 'B - Bueno'),
        ('C', 'C - Satisfactorio'),
        ('D', 'D - Deficiente'),
    )

    id_calificacion = models.BigAutoField(primary_key=True, db_column='id_calificacion')
    id_inscripcion = models.ForeignKey(
        Inscripcion,
        on_delete=models.CASCADE,
        db_column='id_inscripcion',
        related_name='calificaciones'
    )
    id_profesor = models.ForeignKey(
        Profesor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_profesor',
        related_name='calificaciones_registradas'
    )
    calificacion = models.CharField(max_length=2, choices=CALIFICACION_CHOICES, db_column='calificacion')
    fecha_registro = models.DateTimeField(auto_now_add=True, db_column='fecha_registro')

    class Meta:
        db_table = 'calificaciones'
        verbose_name = 'Calificación'
        verbose_name_plural = 'Calificaciones'

    def __str__(self):
        return f"Nota {self.calificacion} - {self.id_inscripcion.id_alumno}"
