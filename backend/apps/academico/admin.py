from django.contrib import admin
from .models import ConfiguracionAsistenciaPublica

@admin.register(ConfiguracionAsistenciaPublica)
class ConfiguracionAsistenciaPublicaAdmin(admin.ModelAdmin):
    list_display = ('fecha_dia', 'activo', 'fecha_vigencia_inicio', 'fecha_vigencia_fin', 'token_acceso')
    list_filter = ('activo',)
    actions = ['activar_seleccionados', 'desactivar_seleccionados']

    @admin.action(description='Activar configuraciones seleccionadas')
    def activar_seleccionados(self, request, queryset):
        updated = queryset.update(activo=True)
        self.message_user(request, f"{updated} configuraciones activadas.")

    @admin.action(description='Desactivar configuraciones seleccionadas')
    def desactivar_seleccionados(self, request, queryset):
        updated = queryset.update(activo=False)
        self.message_user(request, f"{updated} configuraciones desactivadas.")
