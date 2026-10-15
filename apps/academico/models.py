import hashlib

from django.db import models


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
