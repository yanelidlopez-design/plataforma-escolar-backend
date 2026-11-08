import datetime
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.academico.models import ConfiguracionAsistenciaPublica

class ConfiguracionAsistenciaPublicaModelTest(TestCase):
    def test_clean_rejects_weekend(self):
        # 2026-11-07 is a Saturday (weekday=5) according to ISO calendar
        saturday = datetime.date(2026, 11, 7)
        cfg = ConfiguracionAsistenciaPublica(fecha_dia=saturday)
        with self.assertRaises(ValidationError) as cm:
            cfg.full_clean()
        self.assertIn('La configuración solo puede crearse de lunes a viernes', str(cm.exception))

    def test_clean_sets_vigencia(self):
        # Monday 2026-11-02
        monday = datetime.date(2026, 11, 2)
        cfg = ConfiguracionAsistenciaPublica(fecha_dia=monday)
        cfg.full_clean()
        # Expected start: 2026-11-02 07:00 (timezone aware)
        expected_start = timezone.make_aware(datetime.datetime.combine(monday, datetime.time(hour=7)))
        expected_end = expected_start + datetime.timedelta(hours=24)
        self.assertEqual(cfg.fecha_vigencia_inicio, expected_start)
        self.assertEqual(cfg.fecha_vigencia_fin, expected_end)

class GenerateAsistenciaPublicaCommandTest(TestCase):
    def test_command_creates_entry_for_today_when_weekday(self):
        # Force today to be a Monday (2026-11-02) using timezone.override
        monday = datetime.date(2026, 11, 2)
        with override_settings(USE_TZ=False):
            # monkeypatch timezone.localdate to return monday
            original_localdate = timezone.localdate
            timezone.localdate = lambda: monday
            try:
                call_command('generate_asistencia_publica')
            finally:
                timezone.localdate = original_localdate
        self.assertTrue(ConfiguracionAsistenciaPublica.objects.filter(fecha_dia=monday).exists())

class AsistenciaPublicaLinkViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Ensure FRONTEND_URL is defined for the view
        self.frontend_url = 'https://example.com'
        self.override = override_settings(FRONTEND_URL=self.frontend_url)
        self.override.enable()

    def tearDown(self):
        self.override.disable()

    def test_link_returns_active_configuration(self):
        today = timezone.localdate()
        cfg = ConfiguracionAsistenciaPublica.objects.create(
            fecha_dia=today,
            activo=True,
        )
        response = self.client.get('/api/asistencia/link/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        expected_url = f"{self.frontend_url.rstrip('/')}/asistencia/{cfg.token_acceso}"
        self.assertEqual(data['url'], expected_url)
        self.assertEqual(data['token'], cfg.token_acceso)
        self.assertEqual(data['fecha_dia'], str(today))

    def test_link_returns_404_when_no_active(self):
        response = self.client.get('/api/asistencia/link/')
        self.assertEqual(response.status_code, 404)
        self.assertIn('No hay enlace activo para hoy', response.json().get('detail', ''))
