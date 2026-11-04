import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus } from 'lucide-react';
import DataTable from '../common/DataTable';
import AlumnoModal from './AlumnoModal';
import { getAlumnos, createAlumno, updateAlumno, deleteAlumno, exportarAlumnos } from '../../api/alumnos';
import { downloadFile } from '../../utils/downloadFile';
import axiosInstance from '../../api/axiosInstance';

function prepararDatosAlumno(formData) {
  const {
    calle,
    ciudad,
    estado,
    referencia,
    representante_cedula,
    representante_nombre,
    representante_telefono,
    parentesco,
    id_grupo,
    id_profesor_encargado,
    ...datosAlumno
  } = formData;

  const direccionIniciada = [calle, ciudad, estado, referencia].some((valor) => valor?.trim());
  if (direccionIniciada && [calle, ciudad, estado].some((valor) => !valor?.trim())) {
    throw new Error('Completa calle, ciudad y estado para guardar la dirección.');
  }

  const datosRepresentante = {
    cedula: representante_cedula?.trim(),
    nombre: representante_nombre?.trim(),
    telefono: representante_telefono?.trim(),
  };
  const representanteIniciado = Object.values(datosRepresentante).some(Boolean);
  if (representanteIniciado && Object.values(datosRepresentante).some((valor) => !valor)) {
    throw new Error('Completa cédula, nombre y teléfono del representante.');
  }

  const hoy = new Date();
  const fechaHoy = [
    hoy.getFullYear(),
    String(hoy.getMonth() + 1).padStart(2, '0'),
    String(hoy.getDate()).padStart(2, '0'),
  ].join('-');
  const payload = {
    ...datosAlumno,
    fecha_inscripcion_inicial: datosAlumno.fecha_inscripcion_inicial || fechaHoy,
    estatus_general: datosAlumno.estatus_general || 'Activo',
  };
  for (const campo of [
    'peso_kg',
    'talla_cm',
    'ingreso_familiar',
    'numero_hermanos',
    'numero_en_el_planter',
  ]) {
    if (payload[campo] === '') payload[campo] = null;
  }
  if (payload.fecha_egreso === '') payload.fecha_egreso = null;

  if (id_grupo) payload.id_grupo = Number(id_grupo);
  else delete payload.id_grupo;

  if (id_profesor_encargado) {
    payload.id_profesor_encargado = Number(id_profesor_encargado);
  } else {
    delete payload.id_profesor_encargado;
  }

  if (direccionIniciada) {
    payload.direccion = { calle: calle.trim(), ciudad: ciudad.trim(), estado: estado.trim(), referencia: referencia?.trim() || '' };
  }

  if (representanteIniciado) {
    payload.representante = datosRepresentante;
    payload.parentesco = parentesco;
  } else {
    delete payload.parentesco;
  }

  return payload;
}

function describirErrorGuardado(error) {
  const data = error.response?.data;
  if (!data) return error.message || 'Error al guardar el alumno.';
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  return Object.entries(data)
    .map(([campo, mensajes]) => {
      const texto = Array.isArray(mensajes) ? mensajes.join(' ') : String(mensajes);
      return `${campo}: ${texto}`;
    })
    .join('\n') || 'Error al guardar el alumno.';
}

/**
 * AlumnosList - Listado de alumnos con tabla reutilizable.
 * Incluye búsqueda, exportación, modal de registro/edición, acciones y paginación.
 */
export default function AlumnosList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [alumnos, setAlumnos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingAlumno, setEditingAlumno] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [grados, setGrados] = useState([]);
  const [secciones, setSecciones] = useState([]);
  const [gruposAcademicos, setGruposAcademicos] = useState([]);
  const [profesores, setProfesores] = useState([]);
  const [filtros, setFiltros] = useState({ grado: '', seccion: '' });
  const [search, setSearch] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const pageSize = 10;

  useEffect(() => {
    if (searchParams.get('accion') !== 'nuevo') return;
    setEditingAlumno(null);
    setModalOpen(true);
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  const columns = [
    { key: 'id_alumno', label: 'ID' },
    { key: 'cedula_escolar', label: 'Cédula Escolar' },
    {
      key: 'nombre',
      label: 'Nombre Completo',
      render: (row) =>
        `${row.primer_nombre || ''} ${row.segundo_nombre || ''} ${row.primer_apellido || ''} ${row.segundo_apellido || ''}`.trim(),
    },
    { key: 'numero_documento_identidad', label: 'Documento' },
    { key: 'grado_actual', label: 'Grado' },
    { key: 'seccion_actual', label: 'Sección' },
    {
      key: 'estatus_general',
      label: 'Estado',
      render: (row) => {
        const estado = row.estatus_general || 'Sin estado';
        const activo = estado.toLowerCase() === 'activo';
        return (
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
            activo ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
          }`}>
            {estado}
          </span>
        );
      },
    },
  ];

  const fetchAlumnos = useCallback(async (page = 1, searchTerm = search) => {
    setLoading(true);
    setErrorMessage('');
    try {
      const response = await getAlumnos({
        page,
        page_size: pageSize,
        search: searchTerm,
        ...filtros,
      });
      setAlumnos(response.data.results || response.data || []);
      setTotalItems(response.data.count || response.data.length || 0);
    } catch (error) {
      console.error('Error al cargar alumnos:', error);
      setErrorMessage(error.response?.data?.detail || 'No se pudieron cargar los alumnos.');
      setAlumnos([]);
      setTotalItems(0);
    } finally {
      setLoading(false);
    }
  }, [filtros, search]);

  useEffect(() => {
    fetchAlumnos(currentPage, search);
  }, [fetchAlumnos, currentPage, search]);

  useEffect(() => {
    const cargarFiltros = async () => {
      try {
        const [gradosResponse, seccionesResponse, gruposResponse, profesoresResponse] = await Promise.all([
          axiosInstance.get('/core/grados/'),
          axiosInstance.get('/core/secciones/'),
          axiosInstance.get('/academico/grupos/', { params: { page_size: 100 } }),
          axiosInstance.get('/personal/personal/', { params: { page_size: 100 } }),
        ]);
        setGrados(gradosResponse.data.results || gradosResponse.data || []);
        setSecciones(seccionesResponse.data.results || seccionesResponse.data || []);
        setGruposAcademicos(gruposResponse.data.results || gruposResponse.data || []);
        setProfesores(profesoresResponse.data.results || profesoresResponse.data || []);
      } catch (error) {
        console.error('Error al cargar filtros de alumnos:', error);
        setErrorMessage('No se pudieron cargar los catálogos de alumnos y personal.');
      }
    };
    cargarFiltros();
  }, []);

  const handleSave = async (formData) => {
    try {
      const payload = prepararDatosAlumno(formData);
      if (editingAlumno) {
        await updateAlumno(editingAlumno.id_alumno, payload);
      } else {
        await createAlumno(payload);
      }
      setModalOpen(false);
      setEditingAlumno(null);
      fetchAlumnos(currentPage, search);
    } catch (error) {
      console.error('Error al guardar alumno:', error);
      alert(`No se pudo guardar el alumno:\n${describirErrorGuardado(error)}`);
    }
  };

  const handleEdit = (alumno) => {
    setEditingAlumno(alumno);
    setModalOpen(true);
  };

  const handleDelete = async (alumno) => {
    if (!window.confirm(`¿Eliminar al alumno ${alumno.primer_nombre} ${alumno.primer_apellido}?`)) return;
    try {
      await deleteAlumno(alumno.id_alumno);
      fetchAlumnos(currentPage, search);
    } catch (error) {
      console.error('Error al eliminar alumno:', error);
      alert('Error al eliminar el alumno.');
    }
  };

  const handleExport = async (format) => {
    setErrorMessage('');
    try {
      const response = await exportarAlumnos(format, {
        ...(filtros.grado ? { grado: filtros.grado } : {}),
        ...(filtros.seccion ? { seccion: filtros.seccion } : {}),
        ...(search ? { search } : {}),
      });
      await downloadFile(response, `alumnos.${format === 'excel' ? 'xlsx' : format}`);
    } catch (error) {
      console.error(`Error al exportar alumnos en ${format}:`, error);
      setErrorMessage(error.message || error.response?.data?.detail || 'No se pudo exportar a los alumnos.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Encabezado de sección */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Gestión de Alumnos</h2>
          <p className="text-sm text-gray-500">Registro, edición y control del alumnado del plantel.</p>
        </div>
        <button
          onClick={() => {
            setEditingAlumno(null);
            setModalOpen(true);
          }}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Registrar Alumno
        </button>
      </div>

      {errorMessage && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {errorMessage}
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 rounded-xl border border-gray-200 bg-white p-4 md:grid-cols-2">
        <div>
          <label htmlFor="filtro-grado-alumnos" className="mb-1 block text-xs font-medium text-gray-700">
            Grado
          </label>
          <select
            id="filtro-grado-alumnos"
            value={filtros.grado}
            onChange={(event) => {
              setFiltros((prev) => ({ ...prev, grado: event.target.value }));
              setCurrentPage(1);
            }}
            className="select-field"
          >
            <option value="">Todos los grados</option>
            {grados.map((grado) => (
              <option key={grado.id_grado} value={grado.id_grado}>{grado.nombre_grado}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="filtro-seccion-alumnos" className="mb-1 block text-xs font-medium text-gray-700">
            Sección
          </label>
          <select
            id="filtro-seccion-alumnos"
            value={filtros.seccion}
            onChange={(event) => {
              setFiltros((prev) => ({ ...prev, seccion: event.target.value }));
              setCurrentPage(1);
            }}
            className="select-field"
          >
            <option value="">Todas las secciones</option>
            {secciones.map((seccion) => (
              <option key={seccion.id_seccion} value={seccion.id_seccion}>{seccion.nombre_seccion}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Tabla */}
      <DataTable
        columns={columns}
        data={alumnos}
        totalItems={totalItems}
        currentPage={currentPage}
        pageSize={pageSize}
        onPageChange={setCurrentPage}
        onSearch={(query) => {
          setCurrentPage(1);
          setSearch(query);
        }}
        onExportExcel={() => handleExport('excel')}
        onExportPdf={() => handleExport('pdf')}
        onExportCsv={() => handleExport('csv')}
        onEdit={handleEdit}
        onView={handleEdit}
        onDelete={handleDelete}
        loading={loading}
        primaryActionLabel="+ Registrar Alumno"
      />

      {/* Modal de registro/edición */}
      <AlumnoModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSave={handleSave}
        alumno={editingAlumno}
        grupos={gruposAcademicos}
        profesores={profesores}
      />
    </div>
  );
}