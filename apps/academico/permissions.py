from rest_framework import permissions


# Roles que tienen acceso a los viewsets protegidos.
ROLES_PERMITIDOS = ('profesor', 'admin')


def obtener_rol_usuario(user):
    """
    Resuelve el rol de un usuario autenticado sobre `django.contrib.auth.User`.

    El modelo de autenticación es el User estándar de Django (no tiene campo
    `rol`), por lo que el rol se resuelve así, en orden:

    1. Si el objeto expone un atributo `rol` (p. ej. un perfil extendido en el
       futuro), se usa directamente.
    2. Superusuarios de Django se consideran rol 'admin'.
    3. Se busca en la tabla de usuarios del sistema (`core.Usuarios`), que es
       el perfil de roles del dominio (vinculado a Profesores por OneToOne),
       emparejando `nombre_usuario` con `user.username`, sólo si está activo.
    4. Si no se puede resolver un rol, devuelve None (denegar: fail-closed).
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return None

    # 1) Rol directo en el usuario (compatibilidad con perfil/propiedad extendida)
    rol = getattr(user, 'rol', None)
    if isinstance(rol, str) and rol:
        return rol.lower()

    # 2) Superusuario de Django => admin
    if getattr(user, 'is_superuser', False):
        return 'admin'

    # 3) Perfil en la tabla de usuarios del sistema (import diferido para
    #    evitar dependencias de orden de carga de apps)
    from apps.core.models import Usuarios

    registro = Usuarios.objects.filter(
        nombre_usuario=user.username,
        activo=True,
    ).only('rol').first()

    if registro is None:
        return None
    return (registro.rol or '').lower() or None


class EsProfesorOAdmin(permissions.BasePermission):
    """
    Permiso personalizado que solo permite acceso a usuarios con rol
    'profesor' o 'admin', resolviendo el rol sobre el sistema de
    autenticación actual (auth.User + JWT / sesión / basic).

    Fail-closed: si no se puede resolver un rol, se niega el acceso.
    """

    def has_permission(self, request, view):
        rol = obtener_rol_usuario(request.user)
        return rol in ROLES_PERMITIDOS

    def has_object_permission(self, request, view, obj):
        rol = obtener_rol_usuario(request.user)
        return rol in ROLES_PERMITIDOS


class EsAdministrador(permissions.BasePermission):
    """
    Permiso personalizado que solo permite acceso a usuarios con rol
    'admin'. Fail-closed: si no se puede resolver un rol, se niega el acceso.
    """

    def has_permission(self, request, view):
        rol = obtener_rol_usuario(request.user)
        return rol == 'admin'

    def has_object_permission(self, request, view, obj):
        rol = obtener_rol_usuario(request.user)
        return rol == 'admin'


class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """
    Permiso que permite acceso autenticado para escritura y público para lectura.
    """

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or request.user and request.user.is_authenticated
