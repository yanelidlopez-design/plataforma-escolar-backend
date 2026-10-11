"""
Comando de gestión idempotente para garantizar la existencia del nivel
'Preescolar' (Educación Inicial), sus grados 'Inicial 1/2/3' y los
grupos académicos correspondientes.

Uso:
    python manage.py seed_preescolar

Es seguro ejecutarlo múltiples veces: usa get_or_create a nivel de nombre,
por lo que no duplica registros. Se apoya en las tablas reales
(niveles_educativos, grados_academicos, grupos_academicos) gestionadas por el DBA.

Importante: los GRADOS alimentan el filtro de consulta de Alumnos, mientras que
los GRUPOS alimentan el selector de registro de Inscripciones. Si faltan los
grupos, Preescolar aparece en el filtro pero NO al inscribir. Este comando crea
ambos para que la visibilidad sea consistente en toda la app.
"""

from django.core.management.base import BaseCommand
from apps.core.models import NivelesEducativos, GradosAcademicos, Secciones, Turnos, PeriodosAcademicos
from apps.academico.models import GruposAcademicos
from apps.personal.models import Profesores


class Command(BaseCommand):
    help = "Crea (si no existe) el nivel Preescolar, los grados Inicial 1/2/3 y sus grupos académicos."

    # Nombre canónico del nivel y sus grados asociados en orden pedagógico.
    NIVEL_PREESCOLAR = "Preescolar"
    GRADOS_PREESCOLAR = [
        ("Inicial 1", 1),
        ("Inicial 2", 2),
        ("Inicial 3", 3),
    ]

    # Configuración de los grupos a crear (sección y turno por grado).
    # Usa la sección "A", turno "Mañana" y un docente guía si está disponible.
    SECCION_NOMBRE = "A"
    TURNO_NOMBRE = "Mañana"
    CUPO_PREESCOLAR = 20

    def _obtener_docente_guia(self):
        """Primer profesor con categoría 'Profesor' para asignar como director de grupo."""
        return Profesores.objects.filter(categoria="Profesor").order_by("id_profesor").first()

    def handle(self, *args, **options):
        nivel, nivel_creado = NivelesEducativos.objects.get_or_create(
            nombre_nivel=self.NIVEL_PREESCOLAR
        )
        if nivel_creado:
            self.stdout.write(self.style.SUCCESS(
                f"Nivel creado: {self.NIVEL_PREESCOLAR} (id={nivel.id_nivel})"
            ))
        else:
            self.stdout.write(f"Nivel ya existente: {self.NIVEL_PREESCOLAR} (id={nivel.id_nivel})")

        # Dependencias necesarias para crear grupos.
        seccion = Secciones.objects.filter(nombre_seccion=self.SECCION_NOMBRE).first()
        turno = Turnos.objects.filter(nombre_turno=self.TURNO_NOMBRE).first()
        periodo = PeriodosAcademicos.objects.order_by("id_periodo").first()
        docente = self._obtener_docente_guia()

        if not (seccion and turno and periodo):
            self.stdout.write(self.style.WARNING(
                "  No se pudieron crear los grupos: faltan sección/turno/período base."
            ))

        for nombre_grado, orden in self.GRADOS_PREESCOLAR:
            grado, grado_creado = GradosAcademicos.objects.get_or_create(
                id_nivel=nivel,
                nombre_grado=nombre_grado,
                defaults={"orden": orden},
            )
            if grado_creado:
                self.stdout.write(self.style.SUCCESS(
                    f"  Grado creado: {nombre_grado} (orden={orden})"
                ))
            else:
                self.stdout.write(f"  Grado ya existente: {nombre_grado} (id={grado.id_grado})")

            # Crear el grupo académico asociado (necesario para que sea seleccionable
            # al momento de inscribir). Idempotente por (periodo, grado, seccion, turno).
            if seccion and turno and periodo:
                grupo, grupo_creado = GruposAcademicos.objects.get_or_create(
                    periodo=periodo,
                    grado=grado,
                    seccion=seccion,
                    turno=turno,
                    defaults={
                        "nivel": nivel,
                        "profesor_director": docente,
                        "cupo_maximo": self.CUPO_PREESCOLAR,
                    },
                )
                if grupo_creado:
                    self.stdout.write(self.style.SUCCESS(
                        f"    Grupo creado: {nombre_grado} '{self.SECCION_NOMBRE}' "
                        f"({self.TURNO_NOMBRE}) id={grupo.id_grupo}"
                    ))
                else:
                    self.stdout.write(f"    Grupo ya existente: {nombre_grado} (id={grupo.id_grupo})")

        self.stdout.write(self.style.SUCCESS("Seed de Preescolar completado."))
