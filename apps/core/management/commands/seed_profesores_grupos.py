"""
Comando de gestión idempotente para sembrar PROFESORES de prueba con
categoría válida ('Profesor') y asignarlos como docentes guía de los
grupos de Preescolar (Inicial 1/2/3).

Motivación:
    La tabla legacy `profesores` guarda la categoría en la columna
    `especialidad`. Si un registro trae un valor fuera de
    CATEGORIA_CHOICES (p.ej. 'Integral'), el endpoint
    GET /api/personal/personal/?categoria=Profesor NO lo devuelve y el
    selector "Profesor Encargado" del frontend queda vacío. Además, los
    grupos de Preescolar pueden tener id_profesor_principal = NULL.

Uso:
    SEED_PASSWORD=<contraseña> python manage.py seed_profesores_grupos

Es seguro ejecutarlo múltiples veces (get_or_create por nombre_usuario y
por cédula; la asignación de grupo se re-aplica de forma idempotente).
"""

import os

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.hashers import make_password
from apps.core.models import Usuarios
from apps.personal.models import Profesores
from apps.academico.models import GruposAcademicos


# Docentes de Preescolar a crear (uno por grupo Inicial).
# (nombre_usuario, email, primer_nombre, segundo_nombre, primer_apellido,
#  segundo_apellido, cedula)
PROFESORES_PREESCOLAR = [
    ("profe.laura", "laura.mendoza@escuela.edu.ve",
     "Laura", "Cristina", "Mendoza", "Rojas", "V-20000001"),
    ("profe.andrea", "andrea.silva@escuela.edu.ve",
     "Andrea", "Carolina", "Silva", "Pérez", "V-20000002"),
    ("profe.rosa", "rosa.aguilar@escuela.edu.ve",
     "Rosa", "María", "Aguilar", "Linares", "V-20000003"),
]

# Contraseña de prueba: nunca como literal en el código; se toma de la
# variable de entorno SEED_PASSWORD (validada en handle()).
PASSWORD_PRUEBA = os.environ.get("SEED_PASSWORD", "")


class Command(BaseCommand):
    help = (
        "Crea profesores de Preescolar (categoría 'Profesor') y los asigna "
        "como docentes guía de los grupos Inicial 1/2/3."
    )

    def _crear_profesor(self, datos):
        (nombre_usuario, email, p_nombre, s_nombre, p_apellido,
         s_apellido, cedula) = datos

        # 1) Usuario (rol 'profesor'). Idempotente por nombre_usuario.
        usuario, user_creado = Usuarios.objects.get_or_create(
            nombre_usuario=nombre_usuario,
            defaults={
                "email": email,
                "rol": "profesor",
                "activo": True,
                "clave_hash": make_password(PASSWORD_PRUEBA),
            },
        )
        if user_creado:
            self.stdout.write(self.style.SUCCESS(
                f"  Usuario creado: {nombre_usuario} (id={usuario.id_usuario})"
            ))
        else:
            # Asegura credenciales válidas si el usuario ya existía.
            usuario.clave_hash = make_password(PASSWORD_PRUEBA)
            usuario.email = usuario.email or email
            usuario.rol = "profesor"
            usuario.activo = True
            usuario.save()
            self.stdout.write(f"  Usuario existente: {nombre_usuario} (id={usuario.id_usuario})")

        # 2) Profesor. Idempotente por cédula. categoria se persiste en 'especialidad'.
        profesor, prof_creado = Profesores.objects.get_or_create(
            cedula=cedula,
            defaults={
                "id_usuario": usuario,
                "primer_nombre": p_nombre,
                "segundo_nombre": s_nombre,
                "primer_apellido": p_apellido,
                "segundo_apellido": s_apellido,
                "categoria": "Profesor",
            },
        )
        if prof_creado:
            self.stdout.write(self.style.SUCCESS(
                f"  Profesor creado: {p_nombre} {p_apellido} (id={profesor.id_profesor})"
            ))
        else:
            # Corrige categoría inválida heredada (p.ej. 'Integral') y re-vincula usuario.
            profesor.id_usuario = usuario
            profesor.categoria = "Profesor"
            profesor.primer_nombre = p_nombre
            profesor.segundo_nombre = s_nombre
            profesor.primer_apellido = p_apellido
            profesor.segundo_apellido = s_apellido
            profesor.save()
            self.stdout.write(f"  Profesor existente (corregido): {p_nombre} {p_apellido} (id={profesor.id_profesor})")

        return profesor

    def handle(self, *args, **options):
        if not PASSWORD_PRUEBA:
            raise CommandError(
                "SEED_PASSWORD no está definida: exporte la variable de entorno "
                "con la contraseña de prueba antes de ejecutar el seed."
            )
        self.stdout.write("Sembrando profesores de Preescolar...")

        profesores = [self._crear_profesor(d) for d in PROFESORES_PREESCOLAR]

        # Asigna un profesor distinto a cada grupo de Preescolar, ordenado por grado.
        grupos = list(
            GruposAcademicos.objects.filter(
                grado__id_nivel__nombre_nivel="Preescolar"
            ).select_related("grado").order_by("grado__orden", "id_grupo")
        )

        if not grupos:
            self.stdout.write(self.style.WARNING(
                "  No hay grupos de Preescolar. Ejecuta primero: python manage.py seed_preescolar"
            ))
            return

        for idx, grupo in enumerate(grupos):
            profesor = profesores[idx % len(profesores)]
            grupo.profesor_director = profesor
            grupo.save(update_fields=["profesor_director"])
            self.stdout.write(self.style.SUCCESS(
                f"  Grupo {grupo.grado.nombre_grado} (id={grupo.id_grupo}) "
                f"-> docente guía: {profesor.primer_nombre} {profesor.primer_apellido} "
                f"(id={profesor.id_profesor})"
            ))

        self.stdout.write(self.style.SUCCESS(
            "Seed de profesores/asignación de grupos completado."
        ))
