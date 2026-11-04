import { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import DataTable from '../common/DataTable';
import PersonalModal from './PersonalModal';
import { getPersonal, createPersona, updatePersona, deletePersona, exportarPersonal } from '../../api/personal';
import { downloadFile } from '../../utils/downloadFile';

function prepararDatosPersonal(formData) {
  const payload = { ...formData };
  for (const campo of [
    'fecha_nacimiento',
    'fecha_ingreso_ministerio',
    'fecha_ingreso_institucion',
    'numero_hijos',
  ]) {
    if (payload[campo] === '') payload[campo] = null;
  }
  if (payload.numero_hijos !== null && payload.numero_hijos !== undefined) {
    payload.numero_hijos = Number(payload.numero_hijos);
  }
  payload.hijos = (payload.hijos || [])
    .filter((hijo) => [
      hijo.primer_nombre,
      hijo.segundo_nombre,
      hijo.edad,
    ].some((value) => value !== null && value !== undefined && String(value).trim() !== ''))
    .map((hijo) => ({
      ...hijo,
      edad: hijo.edad === '' ? null : Number(hijo.edad),
    }));
  return payload;
}

function describirErrorGuardado(error) {
  const data = error.response?.data;
  if (!data) return error.message || 'Error al guardar el personal.';
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  return Object.entries(data)
    .map(([campo, mensajes]) => {
      const texto = Array.isArray(mensajes) ? mensajes.join(' ') : String(mensajes);
      return `${campo}: ${texto}`;
    })
    .join('\n') || 'Error al guardar el personal.';
}

const CARGOS = [
  'Integral',
  'Profesor',
  'Obrero',
  'Cocinera',
  'Administrativo',
  'Director (Directivo)',
  'Sub-Director (Directivo)',
  'Coordinador (Directivo)',
];

/**
 * PersonalList - Listado de personal con tabla reutilizable.
 * Incluye búsqueda, exportación, modal de registro/edición, acciones y paginación.
 */
export default function PersonalList() {
  const [personal, setPersonal] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPersona, setEditingPersona] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [cargo, setCargo] = useState('');
  const [search, setSearch] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const pageSize = 10;

  const columns = [
    { key: 'id_profesor', label: 'ID' },
    { key: 'cedula', label: 'Cédula' },
    {
      key: 'nombre',
      label: 'Nombre Completo',
      render: (row) =>
        `${row.primer_nombre || ''} ${row.segundo_nombre || ''} ${row.primer_apellido || ''} ${row.segundo_apellido || ''}`.trim(),
    },
    { key: 'cargo', label: 'Cargo' },
    { key: 'categoria', label: 'Categoría' },
    { key: 'dependencia', label: 'Dependencia' },
    { key: 'correo', label: 'Correo' },
    {
      key: 'activo',
      label: 'Estado',
      render: (row) => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          row.activo !== false ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
        }`}>
          {row.activo !== false ? 'Activo' : 'Inactivo'}
        </span>
      ),
    },
  ];

  const fetchPersonal = useCallback(async (page = 1, searchTerm = search) => {
    setLoading(true);
    setErrorMessage('');
    try {
      const response = await getPersonal({
        page,
        page_size: pageSize,
        search: searchTerm,
        cargo,
      });
      setPersonal(response.data.results || response.data || []);
      setTotalItems(response.data.count || response.data.length || 0);
    } catch (error) {
      console.error('Error al cargar personal:', error);
      setErrorMessage(error.response?.data?.detail || 'No se pudo cargar el personal.');
      setPersonal([]);
      setTotalItems(0);
    } finally {
      setLoading(false);
    }
  }, [cargo, search]);

  useEffect(() => {
    fetchPersonal(currentPage, search);
  }, [fetchPersonal, currentPage, search]);

  const handleSave = async (formData) => {
    try {
      const payload = prepararDatosPersonal(formData);
      if (editingPersona) {
        await updatePersona(editingPersona.id_profesor, payload);
      } else {
        await createPersona(payload);
      }
      setModalOpen(false);
      setEditingPersona(null);
      fetchPersonal(currentPage);
    } catch (error) {
      console.error('Error al guardar personal:', error);
      alert(`No se pudo guardar el personal:\n${describirErrorGuardado(error)}`);
    }
  };

  const handleEdit = (persona) => {
    setEditingPersona(persona);
    setModalOpen(true);
  };

  const handleDelete = async (persona) => {
    if (!window.confirm(`¿Eliminar al personal ${persona.primer_nombre} ${persona.primer_apellido}?`)) return;
    try {
      await deletePersona(persona.id_profesor);
      fetchPersonal(currentPage);
    } catch (error) {
      console.error('Error al eliminar personal:', error);
      alert('Error al eliminar el personal.');
    }
  };

  const handleExport = async (format) => {
    setErrorMessage('');
    try {
      const response = await exportarPersonal(format, {
        ...(cargo ? { cargo } : {}),
        ...(search ? { search } : {}),
      });
      await downloadFile(response, `personal.${format === 'excel' ? 'xlsx' : format}`);
    } catch (error) {
      console.error(`Error al exportar personal en ${format}:`, error);
      setErrorMessage(error.message || error.response?.data?.detail || 'No se pudo exportar el personal.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Personal</h2>
          <p className="text-sm text-gray-500">Gestión del personal docente y administrativo del plantel.</p>
        </div>
        <button
          onClick={() => {
            setEditingPersona(null);
            setModalOpen(true);
          }}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Registrar Personal
        </button>
      </div>

      {errorMessage && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {errorMessage}
        </div>
      )}
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <label htmlFor="filtro-cargo-personal" className="block text-xs font-medium text-gray-700 mb-1">
          Filtrar por cargo para listar o exportar
        </label>
        <select
          id="filtro-cargo-personal"
          value={cargo}
          onChange={(event) => {
            setCargo(event.target.value);
            setCurrentPage(1);
          }}
          className="select-field max-w-md"
        >
          <option value="">Todo el personal</option>
          {CARGOS.map((opcion) => <option key={opcion} value={opcion}>{opcion}</option>)}
        </select>
      </div>

      <DataTable
        columns={columns}
        data={personal}
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
        primaryActionLabel="+ Registrar Personal"
      />

      <PersonalModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSave={handleSave}
        persona={editingPersona}
      />
    </div>
  );
}