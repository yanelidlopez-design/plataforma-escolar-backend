"""
Tests for webhook service business logic.
"""
from datetime import date
from decimal import Decimal

from apps.academico.services.webhook_service import (
    procesar_alumno_webhook,
    procesar_inscripcion_webhook,
    _a_booleano,
    _a_decimal,
    _a_entero,
    _a_fecha,
)


class TestWebhookService:
    """Test suite for webhook service business logic."""

    def test_procesar_alumno_missing_required_field(self):
        """Test that missing required fields return error."""
        data = {
            'primer_nombre': 'Juan',
            'primer_apellido': 'Perez'
            # Missing required fields
        }

        alumno, error = procesar_alumno_webhook(data)
        assert alumno is None
        assert 'requerido' in error.lower()

    def test_procesar_alumno_invalid_fecha(self):
        """Test that an unparseable fecha_nacimiento returns a clear error."""
        data = {
            'primer_nombre': 'Juan',
            'primer_apellido': 'Perez',
            'numero_documento_identidad': '99999999',
            'cedula_escolar': 'TEST-CE-001',
            'fecha_nacimiento': 'no-es-fecha',
        }

        alumno, error = procesar_alumno_webhook(data)
        assert alumno is None
        assert 'fecha_nacimiento' in error

    def test_procesar_inscripcion_validation_structure(self):
        """Test that inscription service validates input structure."""
        # Test with empty group_id (should return None, no error)
        inscripcion, error = procesar_inscripcion_webhook(None, {})
        assert inscripcion is None
        assert error is None


class TestNormalizacionWebhook:
    """Helpers de normalización de valores típicos de Google Forms."""

    def test_a_booleano(self):
        """'Sí'/'No' y variantes se convierten a booleanos reales."""
        assert _a_booleano('Sí') is True
        assert _a_booleano('Si') is True
        assert _a_booleano('TRUE') is True
        assert _a_booleano(1) is True
        assert _a_booleano('No') is False
        assert _a_booleano('') is False
        assert _a_booleano(None) is False
        assert _a_booleano(None, por_defecto=True) is True
        assert _a_booleano('otra cosa') is False

    def test_a_decimal(self):
        """Acepta formato anglo y latino; vacío/inválido → None."""
        assert _a_decimal('15500.75') == Decimal('15500.75')
        assert _a_decimal('15.500,75') == Decimal('15500.75')
        assert _a_decimal('70,5') == Decimal('70.5')
        assert _a_decimal('') is None
        assert _a_decimal(None) is None
        assert _a_decimal('abc') is None

    def test_a_entero(self):
        """Convierte strings numéricos a int; vacío/inválido → None."""
        assert _a_entero('3') == 3
        assert _a_entero('3.0') == 3
        assert _a_entero(2) == 2
        assert _a_entero('') is None
        assert _a_entero(None) is None
        assert _a_entero('x') is None

    def test_a_fecha(self):
        """Acepta ISO, dd/mm/yyyy y m/d/yyyy; inválido → None."""
        assert _a_fecha('2010-05-14') == date(2010, 5, 14)
        assert _a_fecha('14/05/2010') == date(2010, 5, 14)
        assert _a_fecha('5/14/2010') == date(2010, 5, 14)
        assert _a_fecha('') is None
        assert _a_fecha(None) is None
        assert _a_fecha('ayer') is None


