from django.db import models

class Direcciones(models.Model):
    id_direccion = models.AutoField(primary_key=True, db_column='id_direccion')
    calle = models.CharField(max_length=255)
    ciudad = models.CharField(max_length=100)
    estado = models.CharField(max_length=100)
    referencia = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'direcciones'
        verbose_name = 'Dirección'
        verbose_name_plural = 'Direcciones'

    def __str__(self):
        return f"{self.estado}, {self.ciudad} - {self.calle}"


class ConfiguracionPlantel(models.Model):
    id_config = models.AutoField(primary_key=True, db_column='id_config')
    nombre_plantel = models.CharField(max_length=200)
    codigo_estadistico = models.CharField(max_length=50, blank=True, null=True)
    codigo_plantel = models.CharField(max_length=50, blank=True, null=True)
    id_director_actual = models.IntegerField(blank=True, null=True)
    id_subdirector_actual = models.IntegerField(blank=True, null=True)
    codigo_dea = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'configuracion_plantel'
        verbose_name = 'Configuración del Plantel'
        verbose_name_plural = 'Configuración del Plantel'

    def __str__(self):
        return self.nombre_plantel

class PeriodosAcademicos(models.Model):
    id_periodo = models.AutoField(primary_key=True, db_column='id_periodo')
    codigo_periodo = models.CharField(max_length=50, unique=True, db_column='codigo_periodo')
    nombre_periodo = models.CharField(max_length=100, db_column='nombre_periodo')
    fecha_inicio = models.DateField(db_column='fecha_inicio')
    fecha_fin = models.DateField(db_column='fecha_fin')
    activo = models.BooleanField(default=True, db_column='activo')

    class Meta:
        managed = False
        db_table = 'periodos_academicos'


class NivelesEducativos(models.Model):
    id_nivel = models.AutoField(primary_key=True, db_column='id_nivel')
    nombre_nivel = models.CharField(max_length=100, db_column='nombre_nivel')

    class Meta:
        managed = False
        db_table = 'niveles_educativos'
        verbose_name = 'Nivel Educativo'
        verbose_name_plural = 'Niveles Educativos'

    def __str__(self):
        return self.nombre_nivel


class Turnos(models.Model):
    id_turno = models.AutoField(primary_key=True, db_column='id_turno')
    nombre_turno = models.CharField(max_length=50, db_column='nombre_turno')
    # Nota: Si tu tabla en MySQL tiene hora_inicio y hora_fin, descoméntalas asegurando su db_column:
    # hora_inicio = models.TimeField(db_column='hora_inicio', blank=True, null=True)
    # hora_fin = models.TimeField(db_column='hora_fin', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'turnos'
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'

    def __str__(self):
        return self.nombre_turno


class GradosAcademicos(models.Model):
    id_grado = models.AutoField(primary_key=True, db_column='id_grado')
    id_nivel = models.ForeignKey(
        NivelesEducativos,
        on_delete=models.PROTECT,
        db_column='id_nivel'
    )
    nombre_grado = models.CharField(max_length=100, db_column='nombre_grado')
    orden = models.SmallIntegerField(db_column='orden')

    class Meta:
        managed = False
        db_table = 'grados_academicos'
        verbose_name = 'Grado Académico'
        verbose_name_plural = 'Grados Académicos'

    def __str__(self):
        return self.nombre_grado


class Secciones(models.Model):
    id_seccion = models.AutoField(primary_key=True, db_column='id_seccion')
    nombre_seccion = models.CharField(max_length=50, db_column='nombre_seccion')

    class Meta:
        managed = False
        db_table = 'secciones'
        verbose_name = 'Sección'
        verbose_name_plural = 'Secciones'

    def __str__(self):
        return self.nombre_seccion

class Usuarios(models.Model):
    ROL_CHOICES = [
        ('admin', 'Administrador'),
        ('profesor', 'Profesor'),
        ('directivo', 'Directivo'),
        ('secretaria', 'Secretaria'),
        ('alumno', 'Alumno'),
    ]

    id_usuario = models.AutoField(primary_key=True, db_column='id_usuario')
    nombre_usuario = models.CharField(max_length=150, unique=True, db_column='nombre_usuario')
    clave_hash = models.CharField(max_length=255, db_column='clave_hash')
    email = models.EmailField(unique=True, db_column='email')
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='profesor', db_column='rol')
    activo = models.BooleanField(default=True, db_column='activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_column='fecha_creacion')

    class Meta:
        managed = False
        db_table = 'usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.nombre_usuario

    # Required for Django authentication
    USERNAME_FIELD = 'nombre_usuario'
    REQUIRED_FIELDS = ['email']

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return self.activo

    @property
    def id(self):
        return self.id_usuario

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.clave_hash)

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.clave_hash = make_password(raw_password)

