from django.db import models

class Profesores(models.Model):
    """
    Personal del plantel (renombrado conceptualmente de 'Profesores' a 'Personal').

    La tabla legacy `profesores` almacena los datos del personal.
    El campo `cargo` reemplaza al antiguo `categoria`.
    """
    CARGO_CHOICES = [
        ('Integral', 'Integral'),
        ('Profesor', 'Profesor'),
        ('Obrero', 'Obrero'),
        ('Cocinera', 'Cocinera'),
        ('Administrativo', 'Administrativo'),
        ('Director (Directivo)', 'Director (Directivo)'),
        ('Sub-Director (Directivo)', 'Sub-Director (Directivo)'),
        ('Coordinador (Directivo)', 'Coordinador (Directivo)'),
    ]

    id_profesor = models.AutoField(primary_key=True, db_column='id_profesor')
    id_usuario = models.OneToOneField(
        'core.Usuarios',
        on_delete=models.CASCADE,
        db_column='id_usuario',
        blank=True,
        null=True
    )
    primer_nombre = models.CharField(max_length=100, db_column='primer_nombre')
    segundo_nombre = models.CharField(max_length=100, blank=True, null=True, db_column='segundo_nombre')
    primer_apellido = models.CharField(max_length=100, db_column='primer_apellido')
    segundo_apellido = models.CharField(max_length=100, blank=True, null=True, db_column='segundo_apellido')
    cedula = models.CharField(max_length=20, unique=True, db_column='cedula')
    telefono = models.CharField(max_length=20, blank=True, null=True, db_column='telefono')
    # Campo de cargo (antes categoria) — se persiste en la columna legacy 'especialidad'
    cargo = models.CharField(max_length=150, choices=CARGO_CHOICES, db_column='especialidad')
    codigo_cargo = models.CharField(max_length=50, blank=True, null=True, db_column='codigo_cargo')
    categoria = models.CharField(max_length=50, blank=True, null=True, db_column='categoria')
    # Datos personales ampliados
    fecha_nacimiento = models.DateField(blank=True, null=True, db_column='fecha_nacimiento')
    talla_zapato = models.CharField(max_length=20, blank=True, null=True, db_column='talla_zapato')
    talla_camisa = models.CharField(max_length=20, blank=True, null=True, db_column='talla_camisa')
    talla_pantalon = models.CharField(max_length=20, blank=True, null=True, db_column='talla_pantalon')
    estado_civil = models.CharField(max_length=50, blank=True, null=True, db_column='estado_civil')
    numero_hijos = models.PositiveIntegerField(blank=True, null=True, db_column='numero_hijos')
    dependencia = models.CharField(max_length=150, blank=True, null=True, db_column='dependencia')
    codigo_dependencia = models.CharField(max_length=50, blank=True, null=True, db_column='codigo_dependencia')
    titulo = models.CharField(max_length=200, blank=True, null=True, db_column='titulo')
    especialidad = models.CharField(max_length=200, blank=True, null=True, db_column='especialidad_campo')
    fecha_ingreso_ministerio = models.DateField(blank=True, null=True, db_column='fecha_ingreso_ministerio')
    fecha_ingreso_institucion = models.DateField(blank=True, null=True, db_column='fecha_ingreso_institucion')
    correo = models.CharField(max_length=200, blank=True, null=True, db_column='correo')
    direccion = models.TextField(blank=True, null=True, db_column='direccion')

    class Meta:
        managed = False
        db_table = 'profesores'
        verbose_name = 'Personal'
        verbose_name_plural = 'Personal'

    @property
    def edad(self):
        """Calcula la edad a partir de la fecha de nacimiento."""
        if self.fecha_nacimiento:
            from django.utils import timezone
            today = timezone.now().date()
            return today.year - self.fecha_nacimiento.year - (
                (today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )
        return None

    @property
    def tiempo_servicio(self):
        """Calcula el tiempo de servicio en años a partir de la fecha de ingreso a la institución."""
        if self.fecha_ingreso_institucion:
            from django.utils import timezone
            today = timezone.now().date()
            return today.year - self.fecha_ingreso_institucion.year - (
                (today.month, today.day) < (self.fecha_ingreso_institucion.month, self.fecha_ingreso_institucion.day)
            )
        return None

    def __str__(self):
        return f"{self.primer_nombre} {self.primer_apellido} - {self.cargo}"


class HijosPersonal(models.Model):
    id_hijo = models.AutoField(primary_key=True, db_column='id_hijo')
    personal = models.ForeignKey(
        Profesores,
        on_delete=models.CASCADE,
        db_column='id_profesor',
        related_name='hijos',
        db_constraint=False,
    )
    primer_nombre = models.CharField(max_length=100, db_column='primer_nombre')
    segundo_nombre = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_column='segundo_nombre',
    )
    edad = models.PositiveSmallIntegerField(db_column='edad')

    class Meta:
        db_table = 'hijos_personal'
        verbose_name = 'Hijo de personal'
        verbose_name_plural = 'Hijos del personal'

    def __str__(self):
        return f"{self.primer_nombre} {self.segundo_nombre or ''}".strip()


class RepresentantesLegales(models.Model):
    id_representante = models.AutoField(primary_key=True, db_column='id_representante')
    id_direccion_residencia = models.ForeignKey(
        'core.Direcciones',
        on_delete=models.SET_NULL,
        db_column='id_direccion_residencia',
        blank=True,
        null=True
    )
    primer_nombre = models.CharField(max_length=100, db_column='primer_nombre')
    segundo_nombre = models.CharField(max_length=100, blank=True, null=True, db_column='segundo_nombre')
    primer_apellido = models.CharField(max_length=100, db_column='primer_apellido')
    segundo_apellido = models.CharField(max_length=100, blank=True, null=True, db_column='segundo_apellido')
    cedula = models.CharField(max_length=20, unique=True, db_column='cedula')
    carnet_patria = models.CharField(max_length=50, blank=True, null=True, db_column='carnet_patria')
    telefono_principal = models.CharField(max_length=20, db_column='telefono_principal')
    telefono_secundario = models.CharField(max_length=20, blank=True, null=True, db_column='telefono_secundario')
    email = models.EmailField(max_length=150, blank=True, null=True, db_column='email')
    ocupacion = models.CharField(max_length=150, blank=True, null=True, db_column='ocupacion')

    class Meta:
        managed = False
        db_table = 'representantes_legales'
        verbose_name = 'Representante Legal'
        verbose_name_plural = 'Representantes Legales'

    def __str__(self):
        return f"{self.primer_nombre} {self.primer_apellido} - C.I. {self.cedula}"


class AlumnoRepresentante(models.Model):
    """
    Tabla relacional pivote entre Alumno y Representante Legal.
    Refleja clave primaria compuesta (id_alumno, id_representante).
    En Django con managed = False, se establece primary_key=True en la relación
    con 'alumno' y unique_together en la Meta para soportar la integridad compuesta.
    """
    alumno = models.OneToOneField(
        'academico.Alumnos',
        on_delete=models.CASCADE,
        db_column='id_alumno',
        primary_key=True,
        related_name='representantes_vinculados',
    )
    representante = models.ForeignKey(
        RepresentantesLegales,
        on_delete=models.CASCADE,
        db_column='id_representante'
    )
    parentesco = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_column='parentesco'
    )
    es_principal = models.BooleanField(
        default=True,
        db_column='es_principal'
    )

    class Meta:
        managed = False
        db_table = 'alumno_representante'
        unique_together = (('alumno', 'representante'),)
        verbose_name = 'Asociación Alumno - Representante'
        verbose_name_plural = 'Asociaciones Alumnos - Representantes'

    def __str__(self):
        return f"Alumno ID {self.alumno_id} <-> Representante ID {self.representante_id}"
