import csv
from io import BytesIO, StringIO
from types import SimpleNamespace

import openpyxl

from apps.academico import reports as reportes_alumnos
from apps.personal.reports_personal import generar_excel_personal


class QuerysetFalso(list):
    def exists(self):
        return bool(self)


class RelacionesFalsas(list):
    def all(self):
        return self


def _alumno_de_prueba():
    direccion = SimpleNamespace(
        calle='Calle 1',
        ciudad='Calabozo',
        estado='Guárico',
        referencia='Frente a la plaza',
    )
    representante = SimpleNamespace(
        primer_nombre='Ana',
        segundo_nombre='María',
        primer_apellido='Pérez',
        segundo_apellido='López',
        cedula='V-123',
        telefono_principal='0412-1234567',
        email='ana@example.com',
    )
    vinculo = SimpleNamespace(
        representante=representante,
        parentesco='Madre',
    )
    grupo = SimpleNamespace(
        grado=SimpleNamespace(nombre_grado='Primer Grado'),
        seccion=SimpleNamespace(nombre_seccion='A'),
    )
    inscripcion = SimpleNamespace(
        grupo=grupo,
        estado_inscripcion='Activa',
    )
    datos = {
        campo: None
        for campo in (
            'cedula_escolar tipo_documento_identidad numero_documento_identidad '
            'primer_nombre segundo_nombre primer_apellido segundo_apellido genero '
            'fecha_nacimiento lugar_nacimiento nacionalidad grupo_sanguineo peso_kg '
            'talla_cm talla_camisa talla_pantalon talla_zapato alergico_a '
            'tratamiento_medico condicion_fisica discapacidad tipo_discapacidad '
            'fecha_inscripcion_inicial estatus_general carnet_patria_codigo '
            'carnet_patria_serial numero_cuenta tipo_cuenta banco '
            'entidad_federal_nacimiento municipio_nacimiento parroquia_nacimiento '
            'apoyo_escolar vacunas_completas estado_civil_padres ingreso_familiar '
            'profesion_madre profesion_padre tipo_vivienda numero_hermanos '
            'numero_en_el_planter observaciones fecha_egreso repitiente'
        ).split()
    }
    datos.update({
        'cedula_escolar': 'CE-1',
        'tipo_documento_identidad': 'V',
        'numero_documento_identidad': '123',
        'primer_nombre': 'Luis',
        'primer_apellido': 'Gómez',
        'genero': 'Masculino',
        'discapacidad': False,
        'apoyo_escolar': True,
        'vacunas_completas': True,
        'repitiente': False,
        'id_direccion_residencia': direccion,
        'id_profesor_encargado': None,
        'representantes_vinculados': RelacionesFalsas([vinculo]),
        'inscripciones': RelacionesFalsas([inscripcion]),
    })
    return SimpleNamespace(**datos)


def test_exportaciones_alumnos_tienen_campos_completos_y_datos_principales():
    alumnos = QuerysetFalso([_alumno_de_prueba()])

    excel = reportes_alumnos.exportar_alumnos_excel(alumnos)
    libro = openpyxl.load_workbook(BytesIO(excel.content), read_only=True)
    hoja = libro.active
    encabezados_excel = next(hoja.iter_rows(values_only=True))
    fila_excel = next(hoja.iter_rows(min_row=2, values_only=True))
    assert len(encabezados_excel) == len(fila_excel)
    assert 'Apoyo Escolar' in encabezados_excel
    assert 'Correo Representante' in encabezados_excel
    assert 'ana@example.com' in fila_excel

    csv_response = reportes_alumnos.exportar_alumnos_csv(alumnos)
    filas_csv = list(csv.reader(StringIO(csv_response.content.decode('utf-8-sig'))))
    assert filas_csv[0] == reportes_alumnos.ALUMNOS_CSV_ENCABEZADOS
    assert len(filas_csv[0]) < len(encabezados_excel)

    pdf_response = reportes_alumnos.exportar_alumnos_pdf(alumnos)
    assert pdf_response.content.startswith(b'%PDF')


def test_excel_personal_exporta_todos_los_campos_del_formulario():
    persona = SimpleNamespace(
        id_usuario=None,
        cedula='V-123',
        primer_nombre='Ana',
        segundo_nombre='María',
        primer_apellido='Pérez',
        segundo_apellido='López',
        telefono='0412-1234567',
        correo='ana@example.com',
        direccion='Calle 1',
        fecha_nacimiento=None,
        estado_civil='Soltera',
        numero_hijos=2,
        cargo='Profesor',
        codigo_cargo='DOC-1',
        categoria='Maestro 1',
        dependencia='Primaria',
        codigo_dependencia='DEP-1',
        titulo='Licenciada',
        especialidad='Matemática',
        fecha_ingreso_ministerio=None,
        fecha_ingreso_institucion=None,
        talla_zapato='38',
        talla_camisa='M',
        talla_pantalon='40',
        hijos=RelacionesFalsas([
            SimpleNamespace(primer_nombre='Luis', segundo_nombre='Andrés', edad=8),
            SimpleNamespace(primer_nombre='Eva', segundo_nombre=None, edad=5),
        ]),
    )

    libro = openpyxl.load_workbook(generar_excel_personal([persona]), read_only=True)
    hoja = libro.active
    encabezados = next(hoja.iter_rows(values_only=True))
    fila = next(hoja.iter_rows(min_row=2, values_only=True))
    assert len(encabezados) == len(fila)
    assert fila[encabezados.index('Correo')] == 'ana@example.com'
    assert fila[encabezados.index('Código de Dependencia')] == 'DEP-1'
    assert fila[encabezados.index('Talla Pantalón')] == '40'
    assert fila[encabezados.index('Detalle de Hijos')] == 'Luis Andrés (8 años); Eva (5 años)'
    hoja_hijos = libro['Hijos']
    filas_hijos = list(hoja_hijos.iter_rows(min_row=2, values_only=True))
    assert filas_hijos == [
        ('V-123', 'Ana María Pérez López', 'Luis', 'Andrés', 8),
        ('V-123', 'Ana María Pérez López', 'Eva', None, 5),
    ]
