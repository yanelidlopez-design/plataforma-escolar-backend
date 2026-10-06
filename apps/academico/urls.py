from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AlumnosViewSet, GruposAcademicosViewSet,
    InscripcionesViewSet, CalificacionesViewSet, AsistenciasViewSet,
    exportar_asistencias_csv, exportar_asistencias_excel, exportar_asistencias_pdf,
    webhook_google_forms, generar_comprobante_inscripcion_pdf
)

router = DefaultRouter()
router.register(r'alumnos', AlumnosViewSet)
router.register(r'grupos', GruposAcademicosViewSet)
router.register(r'inscripciones', InscripcionesViewSet)
router.register(r'calificaciones', CalificacionesViewSet)
router.register(r'asistencias', AsistenciasViewSet)

urlpatterns = [
    path('webhook-google-forms/', webhook_google_forms, name='webhook_google_forms'),
    path('inscripciones/<int:inscripcion_id>/pdf/', generar_comprobante_inscripcion_pdf, name='generar_comprobante_inscripcion_pdf'),
    path('asistencias/exportar-csv/', exportar_asistencias_csv, name='exportar_asistencias_csv'),
    path('asistencias/exportar-excel/', exportar_asistencias_excel, name='exportar_asistencias_excel'),
    path('asistencias/exportar-pdf/', exportar_asistencias_pdf, name='exportar_asistencias_pdf'),
    path('', include(router.urls)),
]
