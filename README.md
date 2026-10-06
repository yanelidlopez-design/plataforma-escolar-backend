# Plataforma Escolar Backend (Django + MariaDB)

Este proyecto proporciona la estructura inicial Backend en Django para la gestión escolar, conectada a una base de datos MariaDB existente (`plataforma_escolar`).

## Estructura de Aplicaciones

- `apps.core`: Configuración del plantel, períodos académicos, niveles, turnos, grados, secciones, direcciones y usuarios.
- `apps.personal`: Profesores, representantes legales y la relación pivot `alumno_representante`.
- `apps.academico`: Alumnos, grupos académicos, inscripciones y calificaciones.

## Características Clave

1. Modelos con `managed = False` mapeados directamente a la base de datos MariaDB `plataforma_escolar`.
2. Conexión de motor `django.db.backends.mysql`.
3. Vistas y Serializers DRF para Alumnos, Inscripciones, Calificaciones, Profesores y más.
4. Permisos personalizados por rol (`EsAdministrador`, `EsProfesor`, `EsProfesorOAdmin`).
