from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AlumnosViewSet, GruposAcademicosViewSet,
    InscripcionesViewSet, CalificacionesViewSet, AsistenciasViewSet,
    exportar_asistencias_csv, exportar_asistencias_excel, exportar_asistencias_pdf,
    exportar_estadistica_mensual_pdf,
    webhook_google_forms, generar_comprobante_inscripcion_pdf,
    estado_exportacion, descargar_exportacion,
    InscripcionDocenteExternaAPIView, AlternarUrlInscripcionAPIView,
    PeriodoInscripcionListCreateAPIView, PeriodoInscripcionDetailAPIView,
    PeriodoInscripcionPublicoAPIView,
    CargaCalificacionesDocenteExternaAPIView, CargaCriteriosDocenteExternaAPIView,
    DescargaInformeDescriptivoAPIView, DescargaBoletaCualitativaAPIView,
    DescargaBoletaCualitativaExcelAPIView,
    ConfiguracionPeriodoCalificacionViewSet,
    RegistrarConstanciaProsecucionAPIView, DescargaConstanciaProsecucionAPIView,
    EvaluacionesCualitativasAdminAPIView,
    CriteriosEvaluacionAdminAPIView,
    EstadisticasDashboardAPIView,
    AsistenciaPublicaGruposAPIView,
    AsistenciaPublicaAlumnosAPIView,
    RegistrarAsistenciaPublicaAPIView,
    ConfiguracionAsistenciaPublicaViewSet,
)

router = DefaultRouter()
router.register(r'alumnos', AlumnosViewSet)
router.register(r'grupos', GruposAcademicosViewSet)
router.register(r'inscripciones', InscripcionesViewSet)
router.register(r'calificaciones', CalificacionesViewSet)
router.register(r'asistencias', AsistenciasViewSet)
router.register(r'periodos-calificacion', ConfiguracionPeriodoCalificacionViewSet)

urlpatterns = [
    path('dashboard/estadisticas/', EstadisticasDashboardAPIView.as_view(), name='dashboard_estadisticas'),
    path('webhook-google-forms/', webhook_google_forms, name='webhook_google_forms'),
    path('inscripciones/<int:inscripcion_id>/pdf/', generar_comprobante_inscripcion_pdf, name='generar_comprobante_inscripcion_pdf'),
    path('asistencias/exportar-csv/', exportar_asistencias_csv, name='exportar_asistencias_csv'),
    path('asistencias/exportar-excel/', exportar_asistencias_excel, name='exportar_asistencias_excel'),
    path('asistencias/exportar-pdf/', exportar_asistencias_pdf, name='exportar_asistencias_pdf'),
    path('asistencias/estadistica-mensual-pdf/', exportar_estadistica_mensual_pdf, name='exportar_estadistica_mensual_pdf'),
    path('inscripcion-externa/', InscripcionDocenteExternaAPIView.as_view(), name='inscripcion_externa'),
    path('calificaciones/cargar-externa/', CargaCalificacionesDocenteExternaAPIView.as_view(), name='carga_calificaciones_externa'),
    path('calificaciones/cargar-criterios-externa/', CargaCriteriosDocenteExternaAPIView.as_view(), name='carga_criterios_externa'),
    path('evaluaciones-cualitativas/', EvaluacionesCualitativasAdminAPIView.as_view(), name='evaluaciones_cualitativas_admin'),
    path('criterios-cualitativos/', CriteriosEvaluacionAdminAPIView.as_view(), name='criterios_cualitativos_admin'),
    path('calificaciones/informe-lapso-pdf/<int:alumno_id>/<int:periodo_id>/', DescargaInformeDescriptivoAPIView.as_view(), name='descarga_informe_descriptivo'),
    path('calificaciones/boleta-cualitativa-pdf/<int:alumno_id>/<int:periodo_id>/', DescargaBoletaCualitativaAPIView.as_view(), name='descarga_boleta_cualitativa'),
    path('calificaciones/boleta-cualitativa-excel/<int:alumno_id>/<int:periodo_id>/', DescargaBoletaCualitativaExcelAPIView.as_view(), name='descarga_boleta_cualitativa_excel'),
    path('calificaciones/prosecucion-final/', RegistrarConstanciaProsecucionAPIView.as_view(), name='registrar_constancia_prosecucion_final'),
    path('calificaciones/prosecucion-final-pdf/<int:alumno_id>/', DescargaConstanciaProsecucionAPIView.as_view(), name='descarga_constancia_prosecucion'),
    path('periodos/', PeriodoInscripcionListCreateAPIView.as_view(), name='listar_periodos'),
    path('periodos/publicos/<str:token>/', PeriodoInscripcionPublicoAPIView.as_view(), name='periodo_publico'),
    path('periodos/<int:pk>/', PeriodoInscripcionDetailAPIView.as_view(), name='detalle_periodo'),
    path('periodos/<int:pk>/alternar-estado/', AlternarUrlInscripcionAPIView.as_view(), name='alternar_estado_periodo'),
    path('exports/<str:reporte_id>/', estado_exportacion, name='estado_exportacion'),
    path('exports/<str:reporte_id>/descarga/', descargar_exportacion, name='descargar_exportacion'),
    path('asistencia-publica/grupos/', AsistenciaPublicaGruposAPIView.as_view(), name='asistencia_publica_grupos'),
    path('asistencia-publica/alumnos/', AsistenciaPublicaAlumnosAPIView.as_view(), name='asistencia_publica_alumnos'),
    path('asistencia-publica/registrar/', RegistrarAsistenciaPublicaAPIView.as_view(), name='asistencia_publica_registrar'),
    path('config/enlaces/asistencia/', ConfiguracionAsistenciaPublicaViewSet.as_view({'get': 'list', 'post': 'create'}), name='config_asistencia_publica'),
    path('config/enlaces/asistencia/<int:pk>/', ConfiguracionAsistenciaPublicaViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='config_asistencia_publica_detalle'),
    path('config/enlaces/asistencia/alternar-estado/', ConfiguracionAsistenciaPublicaViewSet.as_view({'post': 'alternar_estado'}), name='config_asistencia_alternar_estado'),
    path('config/enlaces/asistencia/regenerar-token/', ConfiguracionAsistenciaPublicaViewSet.as_view({'post': 'regenerar_token'}), name='config_asistencia_regenerar_token'),
    path('', include(router.urls)),
]
