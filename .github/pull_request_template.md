## Descripción del código

<!-- Qué cambia, por qué y cómo se prueba. -->

## Cambios de entorno

- [ ] Variables de entorno nuevas o modificadas (actualizar `.env.example`)
- [ ] Dependencias nuevas en `requirements.txt`
- [ ] Migraciones de base de datos (`makemigrations` / `migrate`)
- [ ] Configuración de CI/CD o infraestructura afectada

## Tareas de sub-agentes

- [ ] @sub-manager — supervisión general e infraestructura
- [ ] @db-specialist — persistencia, SQL y core de datos
- [ ] @desarrollador — lógica de negocio y apps
- [ ] @ui-print-dev — reportes y plantillas imprimibles
- [ ] @qa-auditor — suite de pruebas

## Validación pytest

- [ ] `pytest` pasa localmente sin errores
- [ ] `python manage.py check --deploy` sin errores nuevos
- [ ] `python manage.py makemigrations --check --dry-run` sin migraciones pendientes
- [ ] Tests añadidos o actualizados para los cambios realizados
