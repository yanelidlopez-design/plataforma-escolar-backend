"""
Permisos Personalizados RBAC
Plataforma Escolar Backend
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdministrador(BasePermission):
    """
    Permiso exclusivo para usuarios con rol de Administrador.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return hasattr(request.user, 'rol') and request.user.rol == 'ADMINISTRADOR'


class IsDocenteOrAdmin(BasePermission):
    """
    Permite acceso total a Administradores y lectura/escritura de expedientes a Profesores/Docentes.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Permitir métodos de lectura a cualquier usuario autenticado
        if request.method in SAFE_METHODS:
            return True
        
        # Permitir escritura si es Docente o Administrador
        user_rol = getattr(request.user, 'rol', None)
        return user_rol in ['PROFESOR', 'ADMINISTRADOR', 'DIRECTIVO']
