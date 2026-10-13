"""
Tests for webhook service business logic.
"""
import pytest
from apps.academico.services.webhook_service import procesar_alumno_webhook, procesar_inscripcion_webhook


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

    def test_procesar_inscripcion_validation_structure(self):
        """Test that inscription service validates input structure."""
        # Test with empty group_id (should return None, no error)
        inscripcion, error = procesar_inscripcion_webhook(None, {})
        assert inscripcion is None
        assert error is None


