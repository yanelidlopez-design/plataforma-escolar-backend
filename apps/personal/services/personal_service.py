"""
Servicio de alta de personal (SRP).

Centraliza la creación de un registro ``Profesores`` junto con su ``Usuarios``
vinculado, que antes vivía enterrada en ``PersonalViewSet.perform_create``:

* Derivación de rol en ``usuarios`` según la categoría del personal
  (director/coordinador -> directivo, administrativo -> secretaria, resto -> profesor).
* Generación de email único (columna legacy ``usuarios.email`` UNIQUE) y de
  nombre de usuario único (``usuarios.nombre_usuario`` UNIQUE).
* Creación atómica de Usuario + Profesor: si algo falla, no quedan huérfanos.

El módulo no conoce HTTP/Django-REST: recibe datos ya validados por el
serializer y devuelve la instancia creada.
"""

from __future__ import annotations

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils.crypto import get_random_string

from apps.core.models import Usuarios

from ..models import Profesores


class PersonalService:
    """Alta de personal con usuario vinculado, sin lógica HTTP."""

    @staticmethod
    @transaction.atomic
    def crear_personal_con_usuario(validated_data, email_solicitado) -> Profesores:
        """
        Crea el Personal (y su Usuario vinculado si no venía en el payload).

        Args:
            validated_data: ``serializer.validated_data`` de ProfesoresSerializer.
            email_solicitado: email sugerido por el cliente (``request.data['email']``);
                se usa solo si es nuevo en la BD legacy.

        Returns:
            La instancia de ``Profesores`` creada (o la persistida con el
            ``id_usuario`` recibido en el payload).

        Nota: toda la operación corre bajo ``transaction.atomic`` (decorador),
        equivalente al ``with transaction.atomic():`` original que envolvía la
        creación del Usuario y el ``serializer.save()``.
        """
        data = dict(validated_data)
        id_usuario = data.pop('id_usuario', None)

        if id_usuario:
            # El payload trae el vínculo: solo se persiste el Profesor.
            return Profesores.objects.create(**data, id_usuario=id_usuario)

        cedula = data.get('cedula') or ''
        primer_nombre = data.get('primer_nombre') or ''
        primer_apellido = data.get('primer_apellido') or ''
        categoria = data.get('categoria') or 'Profesor'

        # Rol en usuarios según la categoría del personal
        categoria_lower = categoria.lower()
        if 'director' in categoria_lower or 'coordinador' in categoria_lower:
            rol = 'directivo'
        elif categoria_lower == 'administrativo':
            rol = 'secretaria'
        else:
            rol = 'profesor'

        # Email único (la columna usuarios.email es UNIQUE en la BD legacy)
        email = (email_solicitado or '').strip()
        if not email or Usuarios.objects.filter(email=email).exists():
            email = PersonalService._generar_email_unico(cedula)

        usuario = Usuarios.objects.create(
            nombre_usuario=PersonalService._generar_nombre_usuario(
                primer_nombre, primer_apellido, cedula
            ),
            clave_hash=make_password(get_random_string(24)),
            email=email,
            rol=rol,
            activo=True,
        )
        return Profesores.objects.create(**data, id_usuario=usuario)

    @staticmethod
    def _generar_email_unico(cedula) -> str:
        """Email único para la columna legacy ``usuarios.email`` (UNIQUE)."""
        base = f"{(cedula or 'personal').replace('-', '').lower()}@plantel.local"
        local, dominio = base.split('@')
        email = base
        contador = 1
        while Usuarios.objects.filter(email=email).exists():
            email = f"{local}{contador}@{dominio}"
            contador += 1
        return email

    @staticmethod
    def _generar_nombre_usuario(primer_nombre, primer_apellido, cedula) -> str:
        """Nombre de usuario único (``usuarios.nombre_usuario`` UNIQUE)."""
        base = (f"{primer_nombre.split()[0] if primer_nombre else ''}"
                f".{primer_apellido.split()[0] if primer_apellido else ''}").strip('.').lower().replace(' ', '')
        if not base:
            base = f"user{(cedula or '0').replace('-', '')}"
        nombre = base
        contador = 1
        while Usuarios.objects.filter(nombre_usuario=nombre).exists():
            nombre = f"{base}{contador}"
            contador += 1
        return nombre
