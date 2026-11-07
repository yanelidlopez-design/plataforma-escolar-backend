# -*- coding: utf-8 -*-
# Registro del cambio de models.ForeignKey(..., primary_key=True) a
# models.OneToOneField(...) en AlumnoRepresentante.alumno.
# La tabla alumno_representante es managed = False (gestión externa), por lo
# que no hay operaciones de esquema que aplicar en la base de datos.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0003_hijospersonal'),
    ]

    operations = [
        # Migración de estado únicamente: documenta el cambio de tipo de campo
        # sin generar ALTER TABLE, ya que la columna id_alumno ya es PK.
    ]
