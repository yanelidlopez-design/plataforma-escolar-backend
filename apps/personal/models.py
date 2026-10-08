from django.db import models

class Profesores(models.Model):
    id_profesor = models.AutoField(primary_key=True, db_column='id_profesor')
    id_usuario = models.OneToOneField(
        'core.Usuarios',  # Asegúrate de cambiar 'core' por el nombre real de la app donde vive Usuarios si es distinta
        on_delete=models.CASCADE,
        db_column='id_usuario',  # <- Corregido: debe apuntar a la columna id_usuario
        blank=True,
        null=True
    )
    primer_nombre = models.CharField(max_length=100, db_column='primer_nombre')
    segundo_nombre = models.CharField(max_length=100, blank=True, null=True, db_column='segundo_nombre')
    primer_apellido = models.CharField(max_length=100, db_column='primer_apellido')
    segundo_apellido = models.CharField(max_length=100, blank=True, null=True, db_column='segundo_apellido')
    cedula = models.CharField(max_length=20, unique=True, db_column='cedula')
    especialidad = models.CharField(max_length=150, blank=True, null=True, db_column='especialidad')

    class Meta:
        managed = False
        db_table = 'profesores'
        verbose_name = 'Profesor'
        verbose_name_plural = 'Profesores'

    def __str__(self):
        return f"Prof. {self.primer_nombre} {self.primer_apellido} - C.I. {self.cedula}"


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
    alumno= models.ForeignKey(
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
