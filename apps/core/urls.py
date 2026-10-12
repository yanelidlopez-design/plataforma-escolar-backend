from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DireccionesViewSet, ConfiguracionPlantelViewSet, PeriodosAcademicosViewSet,
    NivelesEducativosViewSet, TurnosViewSet, GradosAcademicosViewSet,
    SeccionesViewSet, UsuariosViewSet, custom_token_obtain, custom_token_logout
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
    path('', include(router.urls)),
]
