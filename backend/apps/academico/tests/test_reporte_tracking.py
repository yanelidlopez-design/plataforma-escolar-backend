import json
from pathlib import Path

import pytest
from django.http import HttpResponse

from apps.academico import reports, tasks
from apps.academico.models import Reporte


@pytest.mark.django_db
def test_encolar_exportacion_crea_registro_y_estado(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks, 'EXPORTS_DIR', str(tmp_path))
    monkeypatch.setattr(tasks, 'async_task', lambda *args: 'task-id')

    reporte_id = tasks.encolar_exportacion('alumnos', 'excel', [])

    reporte = Reporte.objects.get(pk=reporte_id)
    assert reporte.modulo == 'alumnos'
    assert reporte.formato == 'excel'
    assert reporte.estado == 'Procesando'
    assert reporte.parametros == {'modulo': 'alumnos', 'formato': 'excel'}
    estado_path = Path(tmp_path) / reporte_id / 'estado.json'
    assert json.loads(estado_path.read_text(encoding='utf-8'))['estatus'] == 'Procesando'


@pytest.mark.django_db
def test_ejecutar_exportacion_persiste_archivo_y_estado(tmp_path, monkeypatch):
    reporte_id = 'a' * 32
    reporte = Reporte.objects.create(
        id=reporte_id,
        modulo='alumnos',
        formato='excel',
    )
    monkeypatch.setattr(tasks, 'EXPORTS_DIR', str(tmp_path))
    monkeypatch.setattr(
        reports,
        'exportar_alumnos_excel',
        lambda queryset: HttpResponse(b'contenido de prueba'),
    )
    tasks._escribir_estado(
        reporte_id,
        {'reporte_id': reporte_id, 'estatus': 'Procesando'},
    )

    tasks.ejecutar_exportacion(reporte_id, 'alumnos', 'excel', [])

    reporte.refresh_from_db()
    assert reporte.estado == 'Completado'
    assert reporte.archivo.name == f'exports/{reporte_id}/alumnos.xlsx'
    assert reporte.tamanio_bytes == len(b'contenido de prueba')
    assert (Path(tmp_path) / reporte_id / 'alumnos.xlsx').read_bytes() == b'contenido de prueba'
