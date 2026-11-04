# Plataforma Escolar

Monorepo de la plataforma escolar: Django sirve la API y el build estático de React/Vite desde un único servicio web.

## Estructura

```text
backend/
  apps/              # core, personal y academico, incluidas sus migraciones
  config/            # settings, urls, ASGI y WSGI
  manage.py
  requirements.txt
frontend/
  package.json
  vite.config.js
  src/
Dockerfile           # build de Vite y runtime Django
docker-compose.yml   # web + MariaDB
```

Los modelos legacy de personal, alumnos, calificaciones y asistencias y sus migraciones ya existían en el backend. Se conservan sus nombres y `managed = False` para no tomar control de tablas existentes. La migración `0010_reporte` añade una tabla Django administrada para registrar el estado y archivo de las exportaciones, con relaciones opcionales a Alumno y Personal.

## Requisitos

- Docker Engine y Docker Compose v2.
- Para ejecutar los proyectos fuera de Docker: Python 3.12, Node.js 20 y npm.

## Desarrollo con Docker

```sh
cp -n .env.example .env
docker compose up --build
```

La imagen compila Vite con Node 20, instala el backend en Python 3.12 y arranca Django en el puerto `8000`. El contenedor espera a que la base de datos esté disponible, ejecuta `ensure_legacy_schema` para crear las tablas legacy que falten sin alterar tablas existentes, ejecuta `python manage.py migrate --noinput` y luego inicia Gunicorn.

- Frontend SPA: <http://localhost:8000/>
- API: <http://localhost:8000/api/>
- Documentación API en modo debug: <http://localhost:8000/swagger/>

Los endpoints existentes están organizados bajo `/api/core/`, `/api/personal/` y `/api/academico/`.

Para detener los contenedores, usa `docker compose down`. Los datos de MariaDB permanecen en el volumen `mariadb_data`; para eliminarlos explícitamente usa `docker compose down -v`.

## Variables de entorno de producción

Configura como mínimo:

- `DATABASE_URL`: URL de MariaDB accesible desde el contenedor (por ejemplo, `mariadb://usuario:clave@host:3306/plataforma`).
- `DJANGO_SECRET_KEY`: clave aleatoria larga y privada.
- `DEBUG=0`.
- `ALLOWED_HOSTS`: dominios públicos separados por comas.
- `CSRF_TRUSTED_ORIGINS`: orígenes HTTPS separados por comas.
- `CORS_ALLOWED_ORIGINS`: orígenes del navegador permitidos, separados por comas.

Configura también las variables SMTP (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`) si se enviarán correos. No uses las credenciales de `.env.example` en producción.

## Deploy en Render

1. Crea un **Web Service** desde el repositorio y selecciona **Docker** como runtime.
2. Usa el `Dockerfile` ubicado en la raíz y deja el build context como la raíz del repositorio.
3. Define las variables de entorno de producción indicadas arriba. `DATABASE_URL` debe apuntar a una instancia MariaDB externa accesible desde Render; Compose no despliega el servicio `db` dentro de Render.
4. Configura el health check en `/` y asigna un disco persistente si el proyecto necesita conservar archivos en `media/`.

El arranque de Render también ejecuta `ensure_legacy_schema` antes de las migraciones. El archivo raíz `docker-entrypoint-initdb.sql` define el esquema estructural completo de las tablas legacy usadas por el backend: usuarios/direcciones, personal, alumnos, períodos/grupos, inscripciones, calificaciones, asistencias y representantes. Todas las instrucciones usan `CREATE TABLE IF NOT EXISTS`; no importan filas ni reemplazan tablas existentes.

## Migraciones y esquema legacy

Las migraciones existentes de `backend/apps/` se conservan y se agrega `academico.0010_reporte`. Varias entidades legacy usan `managed = False`, por lo que `migrate` no crea sus tablas. El entrypoint aplica primero el esquema SQL versionado y luego las migraciones. En una instalación con tablas preexistentes, `CREATE TABLE IF NOT EXISTS` las deja intactas, pero no verifica ni actualiza su estructura; valida previamente que coincidan con los modelos desplegados. Para copiar los registros de otro entorno, restaura un dump validado en la base destino antes de desplegar. El esquema de arranque no incluye datos de ejemplo ni credenciales de usuarios.
