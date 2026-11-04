import pytest
from django.contrib.auth.hashers import make_password
from rest_framework.test import APIClient

from apps.core.models import Usuarios
from apps.personal.models import Profesores


def crear_usuario(nombre, rol, password='Actual-Segura-2025!'):
    return Usuarios.objects.create(
        nombre_usuario=nombre,
        clave_hash=make_password(password),
        email=f'{nombre}@plantel.local',
        rol=rol,
        activo=True,
    )


@pytest.mark.django_db
def test_usuario_cambia_su_contrasena_con_la_actual_correcta(tablas_legacy):
    usuario = crear_usuario('usuario.cambio', 'profesor')
    client = APIClient()
    client.force_authenticate(user=usuario)

    response = client.post('/api/core/usuarios/cambiar-password/', {
        'contrasena_actual': 'Actual-Segura-2025!',
        'contrasena_nueva': 'Nueva-Segura-2026!',
        'confirmar_contrasena': 'Nueva-Segura-2026!',
    }, format='json')

    usuario.refresh_from_db()
    assert response.status_code == 200
    assert usuario.check_password('Nueva-Segura-2026!')
    assert not usuario.check_password('Actual-Segura-2025!')


@pytest.mark.django_db
def test_cambio_rechaza_contrasena_actual_incorrecta(tablas_legacy):
    usuario = crear_usuario('usuario.incorrecta', 'profesor')
    client = APIClient()
    client.force_authenticate(user=usuario)

    response = client.post('/api/core/usuarios/cambiar-password/', {
        'contrasena_actual': 'Incorrecta-2025!',
        'contrasena_nueva': 'Nueva-Segura-2026!',
        'confirmar_contrasena': 'Nueva-Segura-2026!',
    }, format='json')

    assert response.status_code == 400
    usuario.refresh_from_db()
    assert usuario.check_password('Actual-Segura-2025!')


@pytest.mark.django_db
def test_restablecimiento_de_personal_requiere_administrador(tablas_legacy):
    administrador = crear_usuario('administrador', 'admin')
    usuario_personal = crear_usuario('profesor.restablecer', 'profesor')
    persona = Profesores.objects.create(
        id_usuario=usuario_personal,
        primer_nombre='Ana',
        primer_apellido='Pérez',
        cedula='V-100001',
        cargo='Profesor',
    )
    client = APIClient()
    client.force_authenticate(user=administrador)

    response = client.post(
        f'/api/personal/personal/{persona.id_profesor}/restablecer-password/',
        {
            'contrasena_nueva': 'Temporal-Segura-2026!',
            'confirmar_contrasena': 'Temporal-Segura-2026!',
        },
        format='json',
    )

    usuario_personal.refresh_from_db()
    assert response.status_code == 200
    assert usuario_personal.check_password('Temporal-Segura-2026!')
    assert 'contrasena' not in response.data


@pytest.mark.django_db
def test_personal_sin_usuario_vinculado_devuelve_error_claro(tablas_legacy):
    administrador = crear_usuario('administrador.sin-vinculo', 'admin')
    persona = Profesores.objects.create(
        primer_nombre='Luis',
        primer_apellido='Gómez',
        cedula='V-100002',
        cargo='Profesor',
    )
    client = APIClient()
    client.force_authenticate(user=administrador)

    response = client.post(
        f'/api/personal/personal/{persona.id_profesor}/restablecer-password/',
        {
            'contrasena_nueva': 'Temporal-Segura-2026!',
            'confirmar_contrasena': 'Temporal-Segura-2026!',
        },
        format='json',
    )

    assert response.status_code == 409
    assert 'no tiene una cuenta' in response.data['detail']


@pytest.mark.django_db
def test_usuario_no_administrador_no_puede_restablecer_claves(tablas_legacy):
    usuario = crear_usuario('profesor.no-admin', 'profesor')
    persona_usuario = crear_usuario('cuenta.objetivo', 'profesor')
    persona = Profesores.objects.create(
        id_usuario=persona_usuario,
        primer_nombre='Eva',
        primer_apellido='López',
        cedula='V-100003',
        cargo='Profesor',
    )
    client = APIClient()
    client.force_authenticate(user=usuario)

    response = client.post(
        f'/api/personal/personal/{persona.id_profesor}/restablecer-password/',
        {
            'contrasena_nueva': 'Temporal-Segura-2026!',
            'confirmar_contrasena': 'Temporal-Segura-2026!',
        },
        format='json',
    )

    assert response.status_code == 403
    persona_usuario.refresh_from_db()
    assert persona_usuario.check_password('Actual-Segura-2025!')
