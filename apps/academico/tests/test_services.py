"""
Tests for webhook service business logic.
"""
import pytest
from apps.academico.services.webhook_service import procesar_alumno_webhook, procesar_inscripcion_webhook
from apps.academico.models import Alumnos, Inscripciones


@pytest.mark.django_db
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
        assert 'required' in error.lower()

    def test_procesar_alumno_duplicate_document(self):
        """Test that duplicate document ID is rejected."""
        # First create an alumno
        Alumnos.objects.create(
            primer_nombre='Juan',
            primer_apellido='Perez',
            numero_documento_identidad='REMOVED_SECRET78',
            cedula_escolar='TEST123',
            fecha_nacimiento='2010-01-01'
        )

        # Try to create another with same document
        data = {
            'primer_nombre': 'Maria',
            'primer_apellido': 'Gomez',
            'numero_documento_identidad': 'REMOVED_SECRET78',
            'cedula_escolar': 'TEST456',
            'fecha_nacimiento': '2010-01-01'
        }

        alumno, error = procesar_alumno_webhook(data)
        assert alumno is None
        assert 'existe' in error.lower()

    def test_procesar_alumno_success(self):
        """Test successful student creation."""
        data = {
            'primer_nombre': 'Carlos',
            'primer_apellido': 'Lopez',
            'numero_documento_identidad': '87654321',
            'cedula_escolar': 'TEST789',
            'fecha_nacimiento': '2010-01-01'
        }

        alumno, error = procesar_alumno_webhook(data)
        assert alumno is not None
        assert error is None
        assert alumno.primer_nombre == 'Carlos'
        assert alumno.numero_documento_identidad == '87654321'

    def test_procesar_inscripcion_invalid_grupo(self):
        """Test that invalid group ID returns error."""
        # Create a dummy alumno
        alumno = Alumnos.objects.create(
            primer_nombre='Test',
            primer_apellido='User',
            numero_documento_identidad='99999999',
            cedula_escolar='TEST999',
            fecha_nacimiento='2010-01-01'
        )

        # Try to create inscription with non-existent group
        inscripcion, error = procesar_inscripcion_webhook(alumno, {'id_grupo': 99999})
        assert inscripcion is None
        assert error is not None
        assert 'no existe' in error.lower()

    def test_procesar_inscripcion_no_group_id(self):
        """Test that when no group_id is provided, returns None (no error)."""
        alumno = Alumnos.objects.create(
            primer_nombre='Test',
            primer_apellido='User',
            numero_documento_identidad='88888888',
            cedula_escolar='TEST888',
            fecha_nacimiento='2010-01-01'
        )

        inscripcion, error = procesar_inscripcion_webhook(alumno, {})
        assert inscripcion is None
        assert error is None
