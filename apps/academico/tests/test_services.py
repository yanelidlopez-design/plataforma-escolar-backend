"""
Tests for webhook service business logic.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.academico.services.webhook_service import (
    procesar_alumno_webhook,
    procesar_inscripcion_webhook,
    _a_booleano,
    _a_decimal,
    _a_entero,
    _a_fecha,
)
from apps.personal.models import AlumnoRepresentante, Profesores, RepresentantesLegales


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


class TestVinculacionWebhook:
    """Profesor encargado y representante legal en el webhook de alumnos.

    Requiere las tablas legacy (managed=False) creadas por el fixture
    `tablas_legacy` de conftest.py.
    """

    def _payload(self, **extras):
        """Payload base mínimo para crear un alumno."""
        data = {
            'primer_nombre': 'Juan',
            'primer_apellido': 'Pérez',
            'numero_documento_identidad': '30111222',
            'cedula_escolar': 'CE-REP-001',
            'fecha_nacimiento': '2015-05-14',
        }
        data.update(extras)
        return data

    # --- Profesor encargado ---

    def test_profesor_encargado_por_cedula(self, tablas_legacy):
        profesor = Profesores.objects.create(
            cedula='19REMOVED_SECRET',
            primer_nombre='María',
            primer_apellido='López',
            categoria='Profesor',
        )
        alumno, error = procesar_alumno_webhook(
            self._payload(profesor_encargado='19REMOVED_SECRET')
        )
        assert error is None
        assert alumno.id_profesor_encargado == profesor

    def test_profesor_encargado_por_cedula_con_prefijo(self, tablas_legacy):
        """"V-19555444" también matchea (se reducen los dígitos)."""
        profesor = Profesores.objects.create(
            cedula='19555444',
            primer_nombre='María',
            primer_apellido='López',
            categoria='Profesor',
        )
        alumno, error = procesar_alumno_webhook(
            self._payload(profesor_encargado='V-19555444')
        )
        assert error is None
        assert alumno.id_profesor_encargado == profesor

    def test_profesor_encargado_por_nombre_normalizado(self, tablas_legacy):
        """Matchea por nombre completo sin acentos ni dobles espacios."""
        profesor = Profesores.objects.create(
            cedula='20REMOVED_SECRET',
            primer_nombre='José',
            primer_apellido='Muñoz',
            categoria='Profesor',
        )
        alumno, error = procesar_alumno_webhook(
            self._payload(profesor_encargado='jose  muñoz')
        )
        assert error is None
        assert alumno.id_profesor_encargado == profesor

    def test_profesor_encargado_desconocido_no_bloquea(self, tablas_legacy):
        """Si no existe, el alumno se crea igual con FK en None + warning."""
        alumno, error = procesar_alumno_webhook(
            self._payload(profesor_encargado='Nadie Conocido')
        )
        assert error is None
        assert alumno is not None
        assert alumno.id_profesor_encargado is None

    def test_profesor_encargado_ausente(self, tablas_legacy):
        alumno, error = procesar_alumno_webhook(self._payload())
        assert error is None
        assert alumno.id_profesor_encargado is None

    # --- Representante legal ---

    def test_representante_completo_crea_y_vincula(self, tablas_legacy):
        alumno, error = procesar_alumno_webhook(self._payload(
            parentesco='Madre',
            representante={
                'cedula': 'V-10101010',
                'nombre': 'María Perez',
                'telefono': '0412-REMOVED_SECRET7',
                'email': 'maria@example.com',
                'ocupacion': 'Docente',
            },
        ))
        assert error is None

        rep = RepresentantesLegales.objects.get(cedula='V-10101010')
        assert rep.primer_nombre == 'María'
        assert rep.primer_apellido == 'Perez'
        assert rep.telefono_principal == '0412-REMOVED_SECRET7'
        assert rep.email == 'maria@example.com'

        vinculo = AlumnoRepresentante.objects.get(alumno=alumno, representante=rep)
        assert vinculo.parentesco == 'Madre'
        assert vinculo.es_principal is True

    def test_representante_reutiliza_existente_por_cedula(self, tablas_legacy):
        """No duplica: si la cédula ya existe, se vincula al existente."""
        alumno1, error1 = procesar_alumno_webhook(self._payload(
            representante={'cedula': '15151515', 'nombre': 'Pedro Gómez', 'telefono': '0414-9999999'},
        ))
        assert error1 is None
        assert RepresentantesLegales.objects.filter(cedula='15151515').count() == 1

        alumno2, error2 = procesar_alumno_webhook(self._payload(
            numero_documento_identidad='30999888',
            cedula_escolar='CE-REP-002',
            representante={'cedula': '15151515', 'nombre': 'Pedro Gómez', 'telefono': '0414-9999999'},
        ))
        assert error2 is None
        assert RepresentantesLegales.objects.filter(cedula='15151515').count() == 1
        assert AlumnoRepresentante.objects.filter(alumno=alumno1).count() == 1
        assert AlumnoRepresentante.objects.filter(alumno=alumno2).count() == 1

    def test_representante_incompleto_se_ignora(self, tablas_legacy):
        """Sin teléfono → no se crea nada, el alumno se crea igual."""
        alumno, error = procesar_alumno_webhook(self._payload(
            representante={'cedula': '20202020', 'nombre': 'Sin Teléfono'},
        ))
        assert error is None
        assert alumno is not None
        assert RepresentantesLegales.objects.count() == 0
        assert AlumnoRepresentante.objects.count() == 0

    def test_representante_nombre_de_una_palabra(self, tablas_legacy):
        """Nombre de una sola palabra → primer_apellido obligatorio recibe 'S/I'."""
        alumno, error = procesar_alumno_webhook(self._payload(
            representante={'cedula': '30303030', 'nombre': 'Rosario', 'telefono': '0424-1112233'},
        ))
        assert error is None
        rep = RepresentantesLegales.objects.get(cedula='30303030')
        assert rep.primer_nombre == 'Rosario'
        assert rep.primer_apellido == 'S/I'
        assert AlumnoRepresentante.objects.get(alumno=alumno).es_principal is True


