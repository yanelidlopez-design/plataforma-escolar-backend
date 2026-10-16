import os
import re
import shutil
import subprocess  # nosec B404
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

# Identificador válido en MariaDB sin comillas: letras, dígitos y guion bajo
PATRON_TABLA = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def respaldar_tabla_legacy(nombre_tabla):
    """Vuelca una tabla a SQL con mysqldump/mariadb-dump (compatible MariaDB)."""
    if not PATRON_TABLA.match(nombre_tabla):
        raise ValueError(f'Nombre de tabla inválido: {nombre_tabla!r}')

    dump = shutil.which('mariadb-dump') or shutil.which('mysqldump')
    if dump is None:
        raise FileNotFoundError('mysqldump/mariadb-dump no disponible en el PATH')

    args = [dump, '-u', os.environ.get('DB_USER', 'root'),
            os.environ.get('DB_NAME', 'escuela_db'), nombre_tabla]

    salida = Path(tempfile.gettempdir()) / f'{nombre_tabla}.sql'
    with salida.open('w', encoding='utf-8') as archivo_salida:
        subprocess.run(args, shell=False, check=True, stdout=archivo_salida)  # nosec B603


class Command(BaseCommand):
    help = 'Vuelca una tabla legacy a SQL con mysqldump/mariadb-dump (compatible MariaDB)'

    def add_arguments(self, parser):
        parser.add_argument('nombre_tabla', help='Tabla exacta a respaldar (identificador MariaDB)')

    def handle(self, *args, **options):
        tabla = options['nombre_tabla']
        try:
            respaldar_tabla_legacy(tabla)
        except (ValueError, FileNotFoundError) as exc:
            raise CommandError(str(exc))
        ruta = Path(tempfile.gettempdir()) / f'{tabla}.sql'
        self.stdout.write(self.style.SUCCESS(f'Volcado generado: {ruta}'))
