import pytest
from django.contrib.auth.hashers import make_password
from rest_framework.test import APIClient

from apps.core.models import Usuarios
from apps.personal.models import HijosPersonal


@pytest.mark.django_db
def test_personal_guarda_y_actualiza_datos_de_sus_hijos(tablas_legacy):
    administrador = Usuarios.objects.create(
        nombre_usuario='admin.hijos',
        clave_hash=make_password('Clave-Segura-2026!'),
        email='admin.hijos@plantel.local',
        rol='admin',
        activo=True,
    )
    client = APIClient()
    client.force_authenticate(user=administrador)

    response = client.post(
        '/api/personal/personal/',
        {
            'primer_nombre': 'Ana',
            'primer_apellido': 'Pérez',
            'cedula': 'V-200001',
            'cargo': 'Profesor',
            'correo': 'ana.perez@plantel.local',
            'numero_hijos': 2,
            'hijos': [
                {'primer_nombre': 'Luis', 'segundo_nombre': 'Andrés', 'edad': 8},
                {'primer_nombre': 'Eva', 'segundo_nombre': '', 'edad': 5},
            ],
        },
        format='json',
    )

    assert response.status_code == 201
    personal_id = response.data['id_profesor']
    assert response.data['hijos'] == [
        {'primer_nombre': 'Luis', 'segundo_nombre': 'Andrés', 'edad': 8},
        {'primer_nombre': 'Eva', 'segundo_nombre': '', 'edad': 5},
    ]
    assert HijosPersonal.objects.filter(personal_id=personal_id).count() == 2

    response = client.patch(
        f'/api/personal/personal/{personal_id}/',
        {
            'numero_hijos': 2,
            'hijos': [
                {'primer_nombre': 'Luis', 'segundo_nombre': 'Andrés', 'edad': 9},
                {'primer_nombre': 'Eva', 'segundo_nombre': '', 'edad': 6},
            ],
        },
        format='json',
    )

    assert response.status_code == 200
    assert list(
        HijosPersonal.objects.filter(personal_id=personal_id)
        .order_by('id_hijo')
        .values_list('primer_nombre', 'edad')
    ) == [('Luis', 9), ('Eva', 6)]


@pytest.mark.django_db
def test_personal_rechaza_mas_detalles_de_hijos_que_el_total(tablas_legacy):
    usuario = Usuarios.objects.create(
        nombre_usuario='admin.hijos.validacion',
        clave_hash=make_password('Clave-Segura-2026!'),
        email='admin.hijos.validacion@plantel.local',
        rol='admin',
        activo=True,
    )
    client = APIClient()
    client.force_authenticate(user=usuario)

    response = client.post(
        '/api/personal/personal/',
        {
            'primer_nombre': 'Ana',
            'primer_apellido': 'Pérez',
            'cedula': 'V-200002',
            'cargo': 'Profesor',
            'correo': 'ana.validacion@plantel.local',
            'numero_hijos': 1,
            'hijos': [
                {'primer_nombre': 'Luis', 'segundo_nombre': '', 'edad': 8},
                {'primer_nombre': 'Eva', 'segundo_nombre': '', 'edad': 5},
            ],
        },
        format='json',
    )

    assert response.status_code == 400
    assert 'hijos' in response.data
