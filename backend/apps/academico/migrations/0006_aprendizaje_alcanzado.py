from django.db import migrations, models
import django.db.models.deletion


def crear_tabla(apps, schema_editor):
    if schema_editor.connection.vendor == 'mysql':
        sql = """
            CREATE TABLE IF NOT EXISTS `aprendizaje_alcanzado` (
                `id` bigint(20) NOT NULL AUTO_INCREMENT,
                `id_alumno` int(11) NOT NULL,
                `id_periodo` bigint(20) NOT NULL,
                `texto` longtext NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `aprendizaje_alcanzado_alumno_periodo_uniq` (`id_alumno`, `id_periodo`),
                CONSTRAINT `fk_aprendizaje_alcanzado_alumno`
                    FOREIGN KEY (`id_alumno`) REFERENCES `alumnos` (`id_alumno`) ON DELETE CASCADE,
                CONSTRAINT `fk_aprendizaje_alcanzado_periodo`
                    FOREIGN KEY (`id_periodo`) REFERENCES `periodo_calificacion` (`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
    else:
        sql = '''
            CREATE TABLE IF NOT EXISTS "aprendizaje_alcanzado" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                "id_alumno" integer NOT NULL,
                "id_periodo" integer NOT NULL,
                "texto" text NOT NULL,
                UNIQUE ("id_alumno", "id_periodo")
            );
        '''
    schema_editor.execute(sql)


def eliminar_tabla(apps, schema_editor):
    schema_editor.execute(f'DROP TABLE IF EXISTS {schema_editor.quote_name("aprendizaje_alcanzado")}')


class Migration(migrations.Migration):
    dependencies = [
        ('academico', '0005_alumnos_fecha_egreso_repitiente'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(crear_tabla, eliminar_tabla),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='AprendizajeAlcanzado',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('texto', models.TextField(blank=True, db_column='texto', default='')),
                        ('alumno', models.ForeignKey(db_column='id_alumno', on_delete=django.db.models.deletion.CASCADE, to='academico.alumnos')),
                        ('periodo', models.ForeignKey(db_column='id_periodo', on_delete=django.db.models.deletion.CASCADE, to='academico.periodocalificacion')),
                    ],
                    options={
                        'verbose_name': 'Aprendizaje Alcanzado',
                        'verbose_name_plural': 'Aprendizajes Alcanzados',
                        'db_table': 'aprendizaje_alcanzado',
                        'managed': False,
                        'unique_together': {('alumno', 'periodo')},
                    },
                ),
            ],
        ),
    ]