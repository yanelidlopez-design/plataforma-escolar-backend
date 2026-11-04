# Preparar el despliegue en un VPS

Esta configuración publica la aplicación con Docker, Caddy y HTTPS automático.
MariaDB no expone un puerto público y el backend no queda publicado directamente.

Para alojar el sistema en una computadora Windows y compartirlo solo dentro de
la red escolar, sigue la sección [Despliegue en Windows para la red local](#despliegue-en-windows-para-la-red-local).

## Requisitos

- VPS Ubuntu LTS con al menos 2 vCPU y 4 GB de RAM.
- Dominio propio; configura un registro DNS `A` que apunte al VPS antes de iniciar Caddy.
- Puertos TCP 22, 80 y 443 permitidos en el firewall del proveedor. No abras 3306 ni 8000.
- Docker Engine y el complemento Docker Compose instalados.
- Copia de seguridad comprobada de la base escolar y plan de copias periódicas fuera del VPS.

El dominio, VPS, cuenta del proveedor y certificados no se crean desde este repositorio.
No compartas contraseñas, archivos `.env` ni copias de la base por el chat.

## Preparación

Desde el directorio de este repositorio:

1. Copia `.env.production.example` a `.env.production`.
2. Usa el dominio real en `DOMAIN`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y
   `CORS_ALLOWED_ORIGINS`. Genera claves distintas para `SECRET_KEY`,
   `DB_PASSWORD`, `MYSQL_ROOT_PASSWORD` y `WEBHOOK_SECRET_TOKEN`.

   Puedes generar un valor aleatorio con `python3 -c 'import secrets; print(secrets.token_urlsafe(64))'`;
   ejecútalo por separado para cada clave.
3. Conserva `.env.production` fuera de Git y con permisos de propietario:

   ```sh
   chmod 600 .env.production
   ```

4. Antes de alojar datos reales, realiza un respaldo cifrado de la MariaDB actual,
   comprueba que puede restaurarse y define quién conservará copias fuera del VPS.
5. Completa en `.env.production` la configuración SMTP (`EMAIL_HOST`,
   `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`,
   `EMAIL_USE_SSL` y `DEFAULT_FROM_EMAIL`) y define `FRONTEND_URL` con el origen
   HTTPS público. No guardes credenciales SMTP en Git. En desarrollo, el backend
   usa la consola de Django por defecto; el enlace aparece en la salida del servidor.

## Importante: esquema y migración de datos

Este proyecto usa MariaDB y varias tablas escolares `managed=False`. El archivo
`docker-entrypoint-initdb.sql` no crea el esquema completo. Por eso, un volumen
vacío no es una instalación lista para la escuela, y no se debe importar
`planter_educativo_v12.txt` sobre una base existente: contiene operaciones de
creación/reemplazo y un esquema histórico.

No ejecutes `migrate` a ciegas sobre la base real. Primero restaura una copia de
la base actual en un entorno de prueba, comprueba los datos y la compatibilidad
de migraciones. Conserva una copia del respaldo original antes de cualquier
cambio de esquema. La aplicación no ejecuta migraciones automáticamente al
arrancar.

## Publicación

Cuando la copia de prueba ya funcione y el dominio resuelva al VPS:

```sh
docker compose --env-file .env.production -f compose.production.yaml build
```

Antes de activar la versión que guarda los datos de hijos del personal, haz un
respaldo y valida la migración en una copia de la base. La primera orden solo
revisa el plan; la segunda crea la tabla `hijos_personal` en la base indicada:

```sh
docker compose --env-file .env.production -f compose.production.yaml run --rm backend python manage.py migrate personal 0003_hijospersonal --plan
docker compose --env-file .env.production -f compose.production.yaml run --rm backend python manage.py migrate personal 0003_hijospersonal
```

Solo después de verificar la migración, publica ambos servicios:

```sh
docker compose --env-file .env.production -f compose.production.yaml up -d
docker compose --env-file .env.production -f compose.production.yaml ps
```

La primera vez, Caddy solicitará el certificado TLS al recibir tráfico por los
puertos 80/443. Si se restaura una copia de seguridad, detén la aplicación y
valida el procedimiento sobre una copia antes de restaurar en producción.

Para recopilar los archivos estáticos de Django:

```sh
docker compose --env-file .env.production -f compose.production.yaml run --rm backend python manage.py collectstatic --noinput
```

Antes de publicar, revisa la configuración Django de producción:

```sh
docker compose --env-file .env.production -f compose.production.yaml run --rm --no-deps backend python manage.py check --deploy
```

Resuelve los avisos de seguridad; activa HSTS para subdominios únicamente si
todos ellos también usan HTTPS.

## Respaldos

Programa respaldos cifrados fuera del VPS y prueba una restauración en una
instalación aislada antes de depender de ellos. Un ejemplo de exportación
cifrada usando `age` en el VPS:

```sh
mkdir -m 700 -p backups
export AGE_RECIPIENT='age1...'
docker compose --env-file .env.production -f compose.production.yaml exec -T db sh -c 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb-dump --single-transaction --routines --events --user=root "$MARIADB_DATABASE"' | age -r "$AGE_RECIPIENT" > "backups/plataforma-$(date +%F-%H%M).sql.age"
```

Copia el archivo cifrado a un almacenamiento separado del VPS. Guarda la clave
privada de `age` en otro lugar seguro; sin ella no se puede restaurar. No
pruebes una restauración sobre la única base de producción.

## Antes de cargar datos reales

La infraestructura no sustituye una revisión de permisos y privacidad. Este
proyecto contiene endpoints para alumnos, representantes y personal; revisa
los permisos de lectura y escritura por rol, prepara cuentas individuales,
activa respaldos fuera del VPS y prueba recuperación y acceso desde celular
antes de invitar familias o almacenar expedientes reales. Además, `npm audit
--omit=dev` reporta dependencias vulnerables en la interfaz; revisa y actualiza
esas dependencias antes de publicarla con expedientes reales.

## Despliegue en Windows para la red local

La computadora debe permanecer encendida y conectada a la misma red que los
equipos que usarán el sistema. Esta modalidad publica el sitio por HTTP en un
puerto de la red local; no es una configuración para exponerlo en Internet.

### Requisitos y arranque automático

1. Instala Docker Desktop en Windows con el backend WSL2 y habilita su inicio al
   iniciar sesión en Windows: Docker Desktop > Settings > General > **Start
   Docker Desktop when you sign in**.
2. Usa una reserva DHCP en el router para que la computadora conserve una IP
   fija, por ejemplo `192.168.1.9`. Esa dirección permite abrir el sistema desde
   otros equipos de la red.
3. Docker Desktop no inicia sus contenedores antes de que un usuario inicie
   sesión en Windows. Después del inicio de sesión, Docker Desktop arranca y
   Docker Compose vuelve a iniciar automáticamente los contenedores (`restart:
   unless-stopped`). Por tanto, esta opción arranca el sistema automáticamente
   después del inicio de sesión, no antes; no actives el inicio de sesión
   automático de Windows para intentar evitar ese requisito.

### Preparar y publicar

Abre PowerShell en el directorio del proyecto:

```powershell
Copy-Item .env.lan.example .env.lan
notepad .env.lan
```

En `.env.lan`, reemplaza `192.168.1.9` por la IP reservada del equipo en
`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` y
`FRONTEND_URL`. Sustituye también los valores de ejemplo por secretos únicos.
Conserva `.env.lan` fuera de Git y no compartas sus credenciales. Configura
SMTP si se necesita la recuperación de contraseñas por correo.

Antes de usar datos existentes, crea y comprueba un respaldo de la base escolar.
Restaura ese respaldo en la base Docker que usará la instalación y valida la
aplicación con esa copia; un volumen nuevo comienza vacío y no recupera los
registros de otra instancia. Ejecuta las migraciones solo después de comprobar
el respaldo y la restauración:

```powershell
docker compose --env-file .env.lan -f compose.lan.yaml build
docker compose --env-file .env.lan -f compose.lan.yaml run --rm backend python manage.py migrate --plan
docker compose --env-file .env.lan -f compose.lan.yaml run --rm backend python manage.py migrate
docker compose --env-file .env.lan -f compose.lan.yaml run --rm backend python manage.py collectstatic --noinput
docker compose --env-file .env.lan -f compose.lan.yaml up -d
docker compose --env-file .env.lan -f compose.lan.yaml ps
```

La migración `personal.0003_hijospersonal` crea la tabla necesaria para los
nombres y edades de hijos del personal. No uses `down -v`: eliminaría los
volúmenes donde Docker guarda la base y los archivos subidos.

Permite el puerto del sitio solo en el perfil privado de Windows y limita el
origen a la subred local. Ejecuta PowerShell como administrador:

```powershell
New-NetFirewallRule -DisplayName "Plataforma Escolar LAN" -Direction Inbound -Protocol TCP -LocalPort 8080 -RemoteAddress LocalSubnet -Action Allow -Profile Private
```

En otros equipos de la red, abre `http://192.168.1.9:8080` (usa la IP real
reservada). Al cambiar la IP, actualiza las cuatro variables del archivo
`.env.lan` y reinicia los servicios.

Para comprobar o revisar el arranque:

```powershell
docker compose --env-file .env.lan -f compose.lan.yaml ps
docker compose --env-file .env.lan -f compose.lan.yaml logs --tail 100 backend
```

El puerto 8080 queda accesible dentro de la LAN; no configures reenvío de
puertos en el router ni publiques el equipo en Internet. El HTTP de esta
modalidad no cifra el tráfico, por lo que debe limitarse a una red escolar
confiable; para uso externo se requiere HTTPS y un despliegue distinto.
