"""
Enrutador de URLs para la App de Estudiantes
Plataforma Escolar Backend
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AlumnoViewSet, RepresentanteLegalViewSet, DireccionViewSet,
    InscripcionViewSet, CalificacionViewSet
)

router = DefaultRouter()
router.register(r'alumnos', AlumnoViewSet, basename='alumno')
router.register(r'representantes', RepresentanteLegalViewSet, basename='representante')
router.register(r'direcciones', DireccionViewSet, basename='direccion')
router.register(r'inscripciones', InscripcionViewSet, basename='inscripcion')
router.register(r'calificaciones', CalificacionViewSet, basename='calificacion')

urlpatterns = [
    path('', include(router.urls)),
]
