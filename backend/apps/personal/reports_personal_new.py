"""
Motor de reportes binarios del módulo Personal (SRP/LSP).

Concentra la maquetación de exportación en Excel y PDF que antes vivía
inline en ``apps.personal.views``:

* ``generar_excel_personal`` / ``generar_pdf_personal``: listado de personal
  (reciben el queryset ya filtrado por la vista).
* ``generar_excel_alumnos_representantes`` / ``generar_pdf_alumnos_representantes``:
  listado de alumnos y sus representantes legales.

Todas devuelven estrictamente ``io.BytesIO`` con el cursor en posición 0
(buffer en memoria, sin I/O de disco): el transporte HTTP (FileResponse,
headers, content-type) es exclusivamente responsabilidad de las vistas —
así cualquier vista puede consumir estos generadores de forma
intercambiable (Principio de Sustitución de Liskov).
"""

from __future__ import annotations

from io import BytesIO

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Cabeceras compartidas de las hojas de Excel (idénticas en ambos listados).
_FUENTE_CABECERA = Font(name="Arial", size=11, bold=True, color="FFFFFF")
_RELLENO_CABECERA = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")


def _ajustar_ancho_columnas(ws) -> None:
    """Ajusta el ancho de cada columna al contenido máximo (mín. 12)."""
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)


def generar_excel_personal(queryset) -> BytesIO:
    """Listado de personal en Excel (.xlsx) a partir del queryset recibido."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Personal"


