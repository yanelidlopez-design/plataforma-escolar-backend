from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DireccionesViewSet,
    ConfiguracionPlantelViewSet,
    PeriodosAcademicosViewSet,
    NivelesEducativosViewSet,
    TurnosViewSet,
    GradosAcademicosViewSet,
    SeccionesViewSet,
    UsuariosViewSet,
    ConfiguracionAsistenciaPublicaViewSet,
    asistencia_publica_link,
    asistencia_publica_redirect,
    CustomTokenObtainPairView,
    custom_token_logout,
    solicitar_restauracion_contrasena,
    confirmar_restauracion_contrasena,
)

router = DefaultRouter()
router.register(r'direcciones', DireccionesViewSet)
router.register(r'plantel', ConfiguracionPlantelViewSet)
router.register(r'periodos', PeriodosAcademicosViewSet)
router.register(r'niveles', NivelesEducativosViewSet)
router.register(r'turnos', TurnosViewSet)
router.register(r'grados', GradosAcademicosViewSet)
router.register(r'secciones', SeccionesViewSet)
router.register(r'usuarios', UsuariosViewSet)
router.register(r'asistencia-publica', ConfiguracionAsistenciaPublicaViewSet)

urlpatterns = [
    path('token/', CustomTokenObtainPairView.as_view()),
    path('logout/', custom_token_logout),
    path('password-reset/request/', solicitar_restauracion_contrasena, name='solicitar-restauracion-contrasena'),
    path('password-reset/confirm/', confirmar_restauracion_contrasena, name='confirmar-restauracion-contrasena'),
    path('asistencia/link/', asistencia_publica_link, name='asistencia-publica-link'),
    path('asistencia/<str:token>/', asistencia_publica_redirect, name='asistencia-publica-redirect'),
    path('', include(router.urls)),
]
