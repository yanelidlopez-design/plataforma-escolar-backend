from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('academico', '0006_aprendizaje_alcanzado'),
    ]

    operations = [
        migrations.AddField(
            model_name='aprendizajealcanzado',
            name='indicador',
            field=models.CharField(
                blank=True,
                choices=[('PL', 'Plenamente Logrado'), ('L', 'Logrado'), ('PM', 'Por Mejorar'), ('EP', 'En Proceso'), ('I', 'Iniciado')],
                db_column='indicador',
                default='',
                max_length=2,
            ),
        ),
        migrations.AddField(
            model_name='aprendizajealcanzado',
            name='orden',
            field=models.PositiveIntegerField(db_column='orden', default=0),
        ),
        migrations.AddField(
            model_name='aprendizajealcanzado',
            name='criterio',
            field=models.ForeignKey(blank=True, db_column='id_criterio', null=True, on_delete=django.db.models.deletion.SET_NULL, to='academico.criterioevaluacion'),
        ),
        migrations.AlterUniqueTogether(
            name='aprendizajealcanzado',
            unique_together={('alumno', 'periodo', 'orden')},
        ),
    ]