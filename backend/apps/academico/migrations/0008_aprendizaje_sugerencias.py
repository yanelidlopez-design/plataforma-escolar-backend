from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('academico', '0007_aprendizaje_indicador_orden'),
    ]

    operations = [
        migrations.AddField(
            model_name='aprendizajealcanzado',
            name='sugerencias',
            field=models.TextField(blank=True, db_column='sugerencias', null=True),
        ),
    ]