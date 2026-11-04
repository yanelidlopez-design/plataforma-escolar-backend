from django.db import migrations, models


def _actualizar_columnas_alumnos(apps, schema_editor, invertir=False):
    tabla = schema_editor.quote_name('alumnos')
    if 'alumnos' not in schema_editor.connection.introspection.table_names():
        return

    with schema_editor.connection.cursor() as cursor:
        columnas = {
            columna.name
            for columna in schema_editor.connection.introspection.get_table_description(cursor, 'alumnos')
        }

    definiciones = {
        'fecha_egreso': 'date NULL',
        'repitiente': 'boolean NOT NULL DEFAULT 0',
    }
    if invertir:
        for nombre in reversed(tuple(definiciones)):
            if nombre in columnas:
                schema_editor.execute(
                    f'ALTER TABLE {tabla} DROP COLUMN {schema_editor.quote_name(nombre)}'
                )
        return

    for nombre, tipo in definiciones.items():
        if nombre not in columnas:
            schema_editor.execute(
                f'ALTER TABLE {tabla} ADD COLUMN {schema_editor.quote_name(nombre)} {tipo}'
            )


def agregar_columnas_alumnos(apps, schema_editor):
    _actualizar_columnas_alumnos(apps, schema_editor)


def quitar_columnas_alumnos(apps, schema_editor):
    _actualizar_columnas_alumnos(apps, schema_editor, invertir=True)


class Migration(migrations.Migration):
    dependencies = [
        ('academico', '0004_periodocalificacion_criterioevaluacion_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(agregar_columnas_alumnos, quitar_columnas_alumnos),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='alumnos',
                    name='fecha_egreso',
                    field=models.DateField(blank=True, db_column='fecha_egreso', null=True),
                ),
                migrations.AddField(
                    model_name='alumnos',
                    name='repitiente',
                    field=models.BooleanField(db_column='repitiente', default=False),
                ),
            ],
        ),
    ]