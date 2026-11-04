from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Create missing legacy tables without altering existing tables or data.'

    def handle(self, *args, **options):
        schema_path = settings.BASE_DIR / 'docker-entrypoint-initdb.sql'
        try:
            statements = schema_path.read_text(encoding='utf-8').split(';')
        except OSError as exc:
            raise CommandError(f'No se pudo leer el esquema legacy: {schema_path}') from exc

        with connection.cursor() as cursor:
            for statement in statements:
                if statement.strip():
                    cursor.execute(statement)

        self.stdout.write(self.style.SUCCESS('Esquema legacy verificado.'))
