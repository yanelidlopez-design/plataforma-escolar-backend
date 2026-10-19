from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AlumnosViewSet, GruposAcademicosViewSet,
    InscripcionesViewSet, CalificacionesViewSet, AsistenciasViewSet,
    exportar_asistencias_csv, exportar_asistencias_excel, exportar_asistencias_pdf,
    webhook_google_forms, generar_comprobante_inscripcion_pdf,
    estado_exportacion, descargar_exportacion,
    InscripcionDocenteExternaAPIView, AlternarUrlInscripcionAPIView,
    PeriodoInscripcionListCreateAPIView, PeriodoInscripcionDetailAPIView,
    CargaCalificacionesDocenteExternaAPIView, CargaCriteriosDocenteExternaAPIView,
    DescargaInformeDescriptivoAPIView, ConfiguracionPeriodoCalificacionViewSet,
)

router = DefaultRouter()
router.register(r'alumnos', AlumnosViewSet)
router.register(r'grupos', GruposAcademicosViewSet)
router.register(r'inscripciones', InscripcionesViewSet)
router.register(r'calificaciones', CalificacionesViewSet)
router.register(r'asistencias', AsistenciasViewSet)
router.register(r'periodos-calificacion', ConfiguracionPeriodoCalificacionViewSet)

urlpatterns = [
    path('webhook-google-forms/', webhook_google_forms, name='webhook_google_forms'),
    path('inscripciones/<int:inscripcion_id>/pdf/', generar_comprobante_inscripcion_pdf, name='generar_comprobante_inscripcion_pdf'),
    path('asistencias/exportar-csv/', exportar_asistencias_csv, name='exportar_asistencias_csv'),
    path('asistencias/exportar-excel/', exportar_asistencias_excel, name='exportar_asistencias_excel'),
    path('asistencias/exportar-pdf/', exportar_asistencias_pdf, name='exportar_asistencias_pdf'),
    path('inscripcion-externa/', InscripcionDocenteExternaAPIView.as_view(), name='inscripcion_externa'),
    path('calificaciones/cargar-externa/', CargaCalificacionesDocenteExternaAPIView.as_view(), name='carga_calificaciones_externa'),
    path('calificaciones/cargar-criterios-externa/', CargaCriteriosDocenteExternaAPIView.as_view(), name='carga_criterios_externa'),
    path('calificaciones/informe-lapso-pdf/<int:alumno_id>/<int:periodo_id>/', DescargaInformeDescriptivoAPIView.as_view(), name='descarga_informe_descriptivo'),
    path('periodos/', PeriodoInscripcionListCreateAPIView.as_view(), name='listar_periodos'),
    path('periodos/<int:pk>/', PeriodoInscripcionDetailAPIView.as_view(), name='detalle_periodo'),
    path('periodos/<int:pk>/alternar-estado/', AlternarUrlInscripcionAPIView.as_view(), name='alternar_estado_periodo'),
    path('exports/<str:reporte_id>/', estado_exportacion, name='estado_exportacion'),
    path('exports/<str:reporte_id>/descarga/', descargar_exportacion, name='descargar_exportacion'),
    path('', include(router.urls)),
]
