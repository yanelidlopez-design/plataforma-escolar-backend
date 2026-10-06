import os
import django
from datetime import date

# Configurar entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import (
    ConfiguracionPlantel, PeriodosAcademicos, NivelesEducativos,
    Turnos, GradosAcademicos, Secciones, Direcciones, Usuarios
)
from apps.personal.models import Profesores, RepresentantesLegales, AlumnoRepresentante
from apps.academico.models import Alumnos, GruposAcademicos, Inscripciones, Calificaciones, Asistencias

def crear_datos_prueba():
    print("--- INICIANDO CARGA DE DATOS DE PRUEBA ---")

    # 1. Configuración del Plantel (Usando campos reales del modelo)
    config, _ = ConfiguracionPlantel.objects.get_or_create(
        nombre_plantel='Unidad Educativa Modelo',
        defaults={
            'codigo_estadistico': 'EST-00123',
            'codigo_plantel': 'P-987654',
        }
    )
    print("✓ Plantel verificado.")

   # 2. Periodo Académico
    periodo, _ = PeriodosAcademicos.objects.get_or_create(
        codigo_periodo='2026-2027',
        defaults={
           'nombre_periodo': 'Año Escolar 2026-2027',
           'fecha_inicio': date(2026, 9, 15),
           'fecha_fin': date(2027, 7, 15),
           'activo': True
        }
    )
    print(f"✓ Periodo: {periodo.nombre_periodo}")

    # 3. Niveles, Turnos, Grados y Secciones
    nivel, _ = NivelesEducativos.objects.get_or_create(nombre_nivel='Educación Primaria')
    turno, _ = Turnos.objects.get_or_create(nombre_turno='Mañana')
    grado, _ = GradosAcademicos.objects.get_or_create(id_nivel=nivel, nombre_grado='Primer Grado', defaults={'orden': 1})
    seccion, _ = Secciones.objects.get_or_create(nombre_seccion='A')
    print("✓ Parámetros académicos listos.")

    # 4. Dirección
    direccion_alumno, _ = Direcciones.objects.get_or_create(
        calle='Calle Los Rosales, Casa #12',
        ciudad='Caracas',
        estado='Distrito Capital',
        referencia='Sector Norte'
    )
    print("✓ Direcciones creadas.")

    # 5. Usuario y Profesor
    user_profesor, _ = Usuarios.objects.get_or_create(
        nombre_usuario='profe.carlos',
        defaults={
            'email': 'carlos.profesor@colegio.edu.ve',
            'clave_hash': 'pbkdf2_sha256$600000$dummyhash...',
            'rol': 'profesor',
            'activo': True
        }
    )

    profesor, _ = Profesores.objects.get_or_create(
        cedula='V-REMOVED_SECRET78',
        defaults={
            'id_usuario': user_profesor,
            'primer_nombre': 'Carlos',
            'segundo_nombre': 'Enrique',
            'primer_apellido': 'Gómez',
            'segundo_apellido': 'Pérez',
            'especialidad': 'Integral'
        }
    )
    print(f"✓ Profesor creado: {profesor.primer_nombre} {profesor.primer_apellido}")

    # 6. Alumno de Prueba
    user_alumno, _ = Usuarios.objects.get_or_create(
        nombre_usuario='alumno.sofia',
        defaults={
            'email': 'sofia.alumno@colegio.edu.ve',
            'clave_hash': 'pbkdf2_sha256$600000$dummyhash...',
            'rol': 'alumno',
            'activo': True
        }
    )

    alumno, created = Alumnos.objects.get_or_create(
        numero_documento_identidad='35REMOVED_SECRET',
        defaults={
            'id_usuario': user_alumno,
            'id_direccion_residencia': direccion_alumno,
            'primer_nombre': 'Sofía',
            'segundo_nombre': 'Alejandra',
            'primer_apellido': 'García',
            'segundo_apellido': 'López',
            'tipo_documento_identidad': 'V',
            'cedula_escolar': 'ESC-2026-001',
            'fecha_nacimiento': date(2018, 5, 12),
            'genero': 'Femenino',
            'lugar_nacimiento': 'Caracas',
            'nacionalidad': 'Venezolana',
            'grupo_sanguineo': 'O+',
            'peso_kg': 25.5,
            'talla_cm': 120.0,
            'fecha_inscripcion_inicial': date(2026, 9, 1),
            'estatus_general': 'Activo'
        }
    )
    if created:
        print(f"✓ Alumno registrado: {alumno.primer_nombre} {alumno.primer_apellido}")
    else:
        print(f"ℹ️ Alumno ya existía: {alumno.primer_nombre} {alumno.primer_apellido}")

    # 7. Representante Legal
    representante, _ = RepresentantesLegales.objects.get_or_create(
        cedula='V-8765432',
        defaults={
            'id_direccion_residencia': direccion_alumno,
            'primer_nombre': 'Mariana',
            'segundo_nombre': 'Elena',
            'primer_apellido': 'López',
            'segundo_apellido': 'Silva',
            'telefono_principal': '0412-5551234',
            'email': 'mariana.lopez@gmail.com',
            'ocupacion': 'Ingeniera'
        }
    )
    print(f"✓ Representante registrado: {representante.primer_nombre} {representante.primer_apellido}")

    # 8. Relación Alumno - Representante
    AlumnoRepresentante.objects.get_or_create(
        alumno=alumno,
        representante=representante,
        defaults={
            'parentesco': 'Madre',
            'es_principal': True
        }
    )
    print("✓ Relación Alumno-Representante enlazada.")

    # Crear más alumnos y representantes para tener más datos de prueba
    datos_alumnos = [
        {
            'nombre': 'Juan',
            'segundo_nombre': 'Carlos',
            'apellido': 'Rodríguez',
            'segundo_apellido': 'Martínez',
            'cedula': 'V-23456789',
            'cedula_escolar': 'ESC-2026-002',
            'usuario': 'alumno.juan',
            'email': 'juan.alumno@colegio.edu.ve'
        },
        {
            'nombre': 'María',
            'segundo_nombre': 'Elena',
            'apellido': 'Fernández',
            'segundo_apellido': 'López',
            'cedula': 'V-34567890',
            'cedula_escolar': 'ESC-2026-003',
            'usuario': 'alumno.maria',
            'email': 'maria.alumno@colegio.edu.ve'
        },
        {
            'nombre': 'Pedro',
            'segundo_nombre': 'Antonio',
            'apellido': 'García',
            'segundo_apellido': 'Sánchez',
            'cedula': 'V-45678901',
            'cedula_escolar': 'ESC-2026-004',
            'usuario': 'alumno.pedro',
            'email': 'pedro.alumno@colegio.edu.ve'
        },
        {
            'nombre': 'Ana',
            'segundo_nombre': 'Beatriz',
            'apellido': 'Pérez',
            'segundo_apellido': 'Gómez',
            'cedula': 'V-56789012',
            'cedula_escolar': 'ESC-2026-005',
            'usuario': 'alumno.ana',
            'email': 'ana.alumno@colegio.edu.ve'
        },
    ]

    datos_representantes = [
        {
            'nombre': 'José',
            'segundo_nombre': 'Luis',
            'apellido': 'Rodríguez',
            'segundo_apellido': 'Martínez',
            'cedula': 'V-9876543',
            'telefono': '0414-5555678',
            'email': 'jose.rodriguez@gmail.com',
            'ocupacion': 'Arquitecto'
        },
        {
            'nombre': 'Carmen',
            'segundo_nombre': 'Victoria',
            'apellido': 'Fernández',
            'segundo_apellido': 'López',
            'cedula': 'V-8765432',
            'telefono': '0416-5556789',
            'email': 'carmen.fernandez@gmail.com',
            'ocupacion': 'Médica'
        },
        {
            'nombre': 'Roberto',
            'segundo_nombre': 'Carlos',
            'apellido': 'García',
            'segundo_apellido': 'Sánchez',
            'cedula': 'V-7654321',
            'telefono': '0412-5557890',
            'email': 'roberto.garcia@gmail.com',
            'ocupacion': 'Ingeniero'
        },
        {
            'nombre': 'Laura',
            'segundo_nombre': 'Daniela',
            'apellido': 'Pérez',
            'segundo_apellido': 'Gómez',
            'cedula': 'V-6543210',
            'telefono': '0424-5558901',
            'email': 'laura.perez@gmail.com',
            'ocupacion': 'Abogada'
        },
    ]

    for i, datos_al in enumerate(datos_alumnos, start=2):
        user_al, _ = Usuarios.objects.get_or_create(
            nombre_usuario=datos_al['usuario'],
            defaults={
                'email': datos_al['email'],
                'clave_hash': 'pbkdf2_sha256$600000$dummyhash...',
                'rol': 'alumno',
                'activo': True
            }
        )

        alumno_nuevo, _ = Alumnos.objects.get_or_create(
            numero_documento_identidad=datos_al['cedula'],
            defaults={
                'id_usuario': user_al,
                'id_direccion_residencia': direccion_alumno,
                'primer_nombre': datos_al['nombre'],
                'segundo_nombre': datos_al['segundo_nombre'],
                'primer_apellido': datos_al['apellido'],
                'segundo_apellido': datos_al['segundo_apellido'],
                'tipo_documento_identidad': 'V',
                'cedula_escolar': datos_al['cedula_escolar'],
                'fecha_nacimiento': date(2018, 5, 12),
                'genero': 'Masculino' if datos_al['nombre'] in ['Juan', 'Pedro'] else 'Femenino',
                'lugar_nacimiento': 'Caracas',
                'nacionalidad': 'Venezolana',
                'grupo_sanguineo': 'O+',
                'peso_kg': 25.5,
                'talla_cm': 120.0,
                'fecha_inscripcion_inicial': date(2026, 9, 1),
                'estatus_general': 'Activo'
            }
        )
        print(f"✓ Alumno {i} creado: {alumno_nuevo.primer_nombre} {alumno_nuevo.primer_apellido}")

    for i, datos_rep in enumerate(datos_representantes, start=2):
        representante_nuevo, _ = RepresentantesLegales.objects.get_or_create(
            cedula=datos_rep['cedula'],
            defaults={
                'id_direccion_residencia': direccion_alumno,
                'primer_nombre': datos_rep['nombre'],
                'segundo_nombre': datos_rep['segundo_nombre'],
                'primer_apellido': datos_rep['apellido'],
                'segundo_apellido': datos_rep['segundo_apellido'],
                'telefono_principal': datos_rep['telefono'],
                'email': datos_rep['email'],
                'ocupacion': datos_rep['ocupacion']
            }
        )
        print(f"✓ Representante {i} creado: {representante_nuevo.primer_nombre} {representante_nuevo.primer_apellido}")

    # Crear relaciones adicionales alumno-representante
    alumnos_lista = Alumnos.objects.all()
    representantes_lista = RepresentantesLegales.objects.all()

    for alum in alumnos_lista[1:]:  # Saltar el primero que ya existe
        for rep in representantes_lista[1:]:  # Saltar el primero que ya existe
            AlumnoRepresentante.objects.get_or_create(
                alumno=alum,
                representante=rep,
                defaults={
                    'parentesco': 'Padre' if rep.primer_nombre in ['José', 'Roberto'] else 'Madre',
                    'es_principal': False
                }
            )

    print("✓ Relaciones adicionales Alumno-Representante creadas.")

    # 9. Grupo Académico
    grupo, _ = GruposAcademicos.objects.get_or_create(
        periodo=periodo,         # <- Cambiado de id_periodo= a periodo=
        nivel=nivel,             # <- Cambiado de id_nivel= a nivel=
        grado=grado,             # <- Cambiado de id_grado= a grado=
        seccion=seccion,         # <- Cambiado de id_seccion= a seccion=
        turno=turno,             # <- Cambiado de id_turno= a turno=
        defaults={
            'profesor_principal': profesor, # <- Cambiado de id_profesor_principal a profesor_principal
            'cupo_maximo': 30,
        }
    )

    print("✓ Grupo académico configurado.")

    # 10. Inscripción
    from datetime import datetime
    Inscripciones.objects.get_or_create(
        alumno=alumno,
        grupo=grupo,
        defaults={
            'fecha_inscripcion': datetime.now(),
            'estado_inscripcion': 'Activa',
            'monto_pago': 150.00,
            'referencia_bancaria': 'REF-987654321'
        }
    )

    print("✓ Alumno inscrito exitosamente en el grupo.")

    # 11. Crear datos de prueba para asistencias
    print("\n--- CREANDO DATOS DE ASISTENCIAS ---")
    from datetime import datetime, timedelta

    # Obtener alumnos y grupo
    alumnos_lista = Alumnos.objects.all()
    if not alumnos_lista:
        print("⚠️ No hay alumnos para crear asistencias")
    else:
        # Crear asistencias para los últimos 5 días
        fecha_hoy = date.today()
        estados = ['P', 'P', 'P', 'A', 'T', 'J']  # Pesos para distribución aleatoria

        for dia in range(5):  # Últimos 5 días
            fecha_actual = fecha_hoy - timedelta(days=dia)

            for alumno in alumnos_lista:
                # Asignar estado aleatorio con mayor probabilidad de presente
                import random
                estado = random.choice(estados)

                # Crear registro de asistencia
                Asistencias.objects.get_or_create(
                    fecha=fecha_actual,
                    alumno=alumno,
                    grupo=grupo,
                    defaults={
                        'estado': estado,
                        'observaciones': 'Registro automático de prueba' if estado in ['A', 'T', 'J'] else '',
                        'profesor_registro': profesor
                    }
                )

        print(f"✓ Asistencias creadas para {alumnos_lista.count()} alumnos en los últimos 5 días")

    print("\n--- ¡DATOS DE PRUEBA CARGADOS EXITOSAMENTE! ---")

if __name__ == '__main__':
    crear_datos_prueba()
