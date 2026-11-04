import datetime
from django.utils import timezone
from apps.academico.models import PeriodoCalificacion


def run():
    """
    Pobla la base de datos local con el PeriodoCalificacion ID=1
    para resolver el cortocircuito del 404 en el informe descriptivo.
    """
    # Forzar la creación o actualización del ID=1 usando los campos reales del modelo legacy
    periodo, creado = PeriodoCalificacion.objects.get_or_create(
        id=1,
        defaults={
            'numero_periodo': 1,
            'token_acceso': 'token_prueba_docente_123',
            'activo_manual': True,
            'fecha_limite': timezone.now() + datetime.timedelta(days=30)
        }
    )

    if creado:
        print("✅ Éxito: PeriodoCalificacion con ID=1 creado y configurado como abierto.")
    else:
        # Si ya existe, nos aseguramos de dejarlo abierto para las pruebas del frontend
        periodo.activo_manual = True
        periodo.fecha_limite = timezone.now() + datetime.timedelta(days=30)
        periodo.save(update_fields=['activo_manual', 'fecha_limite'])
        print("ℹ️ Información: El PeriodoCalificacion con ID=1 ya existía. Se forzó su apertura y vigencia.")


if __name__ == '__main__':
    run()
