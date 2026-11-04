from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.hashers import make_password
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from apps.core.models import Usuarios


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='https://plantel.example',
)
def test_solicitud_y_confirmacion_de_recuperacion(tablas_legacy):
    usuario = Usuarios.objects.create(
        nombre_usuario='usuario.recuperacion',
        clave_hash=make_password('Clave-anterior-2026!'),
        email='usuario@plantel.example',
        rol='profesor',
        activo=True,
    )
    client = APIClient(REMOTE_ADDR='192.0.2.21')

    response = client.post(
        '/api/core/password-reset/request/',
        {'email': usuario.email},
        format='json',
    )

    assert response.status_code == 202
    assert len(mail.outbox) == 1
    assert usuario.email in mail.outbox[0].to
    reset_link = next(
        word for word in mail.outbox[0].body.split()
        if word.startswith('https://plantel.example/')
    )
    query = parse_qs(urlparse(reset_link).query)
    uid = query['uid'][0]
    token = query['token'][0]

    response = client.post(
        '/api/core/password-reset/confirm/',
        {
            'uid': uid,
            'token': token,
            'contrasena_nueva': 'Clave-nueva-2026!',
            'confirmar_contrasena': 'Clave-nueva-2026!',
        },
        format='json',
    )

    usuario.refresh_from_db()
    assert response.status_code == 200
    assert usuario.check_password('Clave-nueva-2026!')
    assert not usuario.check_password('Clave-anterior-2026!')

    response = client.post(
        '/api/core/password-reset/confirm/',
        {
            'uid': uid,
            'token': token,
            'contrasena_nueva': 'Otra-clave-2026!',
            'confirmar_contrasena': 'Otra-clave-2026!',
        },
        format='json',
    )
    assert response.status_code == 400


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def test_solicitud_no_revela_si_el_correo_existe(tablas_legacy):
    client = APIClient(REMOTE_ADDR='192.0.2.22')

    response = client.post(
        '/api/core/password-reset/request/',
        {'email': 'no-existe@plantel.example'},
        format='json',
    )

    assert response.status_code == 202
    assert response.data == {
        'detail': (
            'Si el correo está asociado a una cuenta activa, recibirás '
            'instrucciones para restablecer la contraseña.'
        )
    }
    assert not mail.outbox


@pytest.mark.django_db
def test_confirmacion_rechaza_token_invalido(tablas_legacy):
    client = APIClient(REMOTE_ADDR='192.0.2.23')

    response = client.post(
        '/api/core/password-reset/confirm/',
        {
            'uid': 'MQ',
            'token': 'token-invalido',
            'contrasena_nueva': 'Clave-nueva-2026!',
            'confirmar_contrasena': 'Clave-nueva-2026!',
        },
        format='json',
    )

    assert response.status_code == 400
    assert response.data['token'] == ['El enlace no es válido o ha expirado.']
