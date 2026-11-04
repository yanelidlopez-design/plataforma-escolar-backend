from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DireccionesViewSet, ConfiguracionPlantelViewSet, PeriodosAcademicosViewSet,
    NivelesEducativosViewSet, TurnosViewSet, GradosAcademicosViewSet,
    SeccionesViewSet, UsuariosViewSet, custom_token_obtain, custom_token_logout,
    solicitar_restauracion_contrasena, confirmar_restauracion_contrasena
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

urlpatterns = [
    path('token/', custom_token_obtain),
    path('logout/', custom_token_logout),
    path('password-reset/request/', solicitar_restauracion_contrasena, name='solicitar-restauracion-contrasena'),
    path('password-reset/confirm/', confirmar_restauracion_contrasena, name='confirmar-restauracion-contrasena'),
    path('', include(router.urls)),
]
