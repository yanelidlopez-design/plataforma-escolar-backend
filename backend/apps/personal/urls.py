from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    exportar_alumnos_representantes_csv,
    exportar_alumnos_representantes_excel,
    exportar_alumnos_representantes_pdf,
    PersonalViewSet,
    RepresentantesLegales,
    AlumnoRepresentanteViewSet
)

router = DefaultRouter()
# Alias del módulo renombrado a 'Personal' (ruta canónica usada por el frontend)
router.register(r'personal', PersonalViewSet, basename='personal')
# Endpoint principal con nombre 'personal-con-cargos'
router.register(r'personal-con-cargos', PersonalViewSet, basename='personal-con-cargos')
router.register(r'representantes', RepresentantesLegales)
router.register(r'alumno-representante', AlumnoRepresentanteViewSet)

urlpatterns = [
    path('exportar-csv/', exportar_alumnos_representantes_csv, name='exportar_alumnos_representantes_csv'),
    path('exportar-excel/', exportar_alumnos_representantes_excel, name='exportar_excel'),
    path('exportar-pdf/', exportar_alumnos_representantes_pdf, name='exportar_pdf'),
    path('', include(router.urls)),
]