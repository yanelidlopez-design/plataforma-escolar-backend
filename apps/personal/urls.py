from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProfesoresViewSet, RepresentantesLegalesViewSet, AlumnoRepresentanteViewSet, exportar_alumnos_representantes_csv, exportar_alumnos_representantes_excel, exportar_alumnos_representantes_pdf

router = DefaultRouter()
router.register(r'profesores', ProfesoresViewSet)
router.register(r'representantes', RepresentantesLegalesViewSet)
router.register(r'alumno-representante', AlumnoRepresentanteViewSet)

urlpatterns = [
    path('exportar-csv/', exportar_alumnos_representantes_csv, name='exportar_alumnos_representantes_csv'),
    path('exportar-excel/', exportar_alumnos_representantes_excel, name='exportar_excel'),
    path('exportar-pdf/', exportar_alumnos_representantes_pdf, name='exportar_pdf'),
    path('', include(router.urls)),  
]
