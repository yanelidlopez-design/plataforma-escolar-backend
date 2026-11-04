import { useState, useEffect } from 'react';
import { Plus, Globe, Link, Edit, Trash2, RotateCcw } from 'lucide-react';
import ExportButtons from '../common/ExportButtons';
import UrlExternaModal from './UrlExternaModal';
import {
  getUrlsExternas,
  createUrlExterna,
  updateUrlExterna,
  alternarEstadoUrlExterna,
  deleteUrlExterna,
} from '../../api/urlsExternas';

/**
 * UrlsExternasList - Gestión de URLs externas dinámicas.
 * Permite listar, editar slugs, cambiar estado (Activo/Inactivo con Switch)
 * y gestionar fechas de expiración.
 */
export default function UrlsExternasList() {
  const [urls, setUrls] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUrl, setEditingUrl] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const pageSize = 10;

  const columns = [
    { key: 'token_acceso', label: 'Enlace público' },
    { key: 'nombre', label: 'Nombre' },
    { key: 'fecha_inicio', label: 'Fecha Inicio' },
    { key: 'fecha_fin', label: 'Fecha Expiración' },
    {
      key: 'activo',
      label: 'Estado',
      render: (row) => (
        <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
          row.activo_manual ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
        }`}>
          {row.activo_manual ? 'Activo' : 'Inactivo'}
        </span>
      ),
    },
  ];

  const fetchUrls = async () => {
    setLoading(true);
    try {
      const response = await getUrlsExternas({ page: currentPage, page_size: pageSize });
      const data = response.data.results || response.data || [];
      setUrls(data);
      setTotalItems(response.data.count || data.length || 0);
    } catch (error) {
      console.error('Error al cargar URLs externas:', error);
      setUrls([]);
      setTotalItems(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUrls();
  }, [currentPage]);

  const handleSave = async (formData) => {
    setErrorMessage('');
    try {
      if (editingUrl) {
        await updateUrlExterna(editingUrl.id, formData);
      } else {
        await createUrlExterna(formData);
      }
      setModalOpen(false);
      setEditingUrl(null);
      await fetchUrls();
    } catch (error) {
      console.error('Error al guardar URL externa:', error);
      setErrorMessage(error.response?.data?.detail || 'Error al guardar la URL externa.');
    }
  };

  const handleAlternarEstado = async (url) => {
    setErrorMessage('');
    try {
      await alternarEstadoUrlExterna(url.id, !url.activo_manual);
      await fetchUrls();
    } catch (error) {
      console.error('Error al alternar estado:', error);
      setErrorMessage(error.response?.data?.detail || error.response?.data?.error || 'Error al cambiar el estado de la URL.');
    }
  };

  const handleEdit = (url) => {
    setEditingUrl(url);
    setModalOpen(true);
  };

  const handleDelete = async (url) => {
    if (!window.confirm(`¿Eliminar la URL externa "${url.nombre}"?`)) return;
    setErrorMessage('');
    try {
      await deleteUrlExterna(url.id);
      await fetchUrls();
    } catch (error) {
      console.error('Error al eliminar URL externa:', error);
      setErrorMessage(error.response?.data?.detail || error.response?.data?.error || 'Error al eliminar la URL externa.');
    }
  };

  const handleExportar = (format) => {
    // Se conectará a endpoints de exportación cuando estén disponibles
    console.log('Exportar URLs a', format);
  };

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Globe className="w-5 h-5" /> Configuración de Enlaces Externos
          </h2>
          <p className="text-sm text-gray-500">
            Gestión de slugs, estados (Activo/Inactivo) y fechas de expiración de formularios externos.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchUrls}
            disabled={loading}
            className="btn-secondary flex items-center gap-2"
          >
            <RotateCcw className="w-4 h-4" /> Actualizar
          </button>
          <button
            onClick={() => {
              setEditingUrl(null);
              setModalOpen(true);
            }}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Nueva URL Externa
          </button>
        </div>
      </div>

      {errorMessage && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {errorMessage}
        </div>
      )}

      {/* Tabla de URLs externas */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">
            URLs Externas Registradas ({totalItems})
          </h3>
          <div className="flex gap-2">
            <ExportButtons
              onExportExcel={() => handleExportar('excel')}
              onExportPdf={() => handleExportar('pdf')}
              onExportCsv={() => handleExportar('csv')}
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider"
                  >
                    {col.label}
                  </th>
                ))}
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider text-center">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={columns.length + 1} className="px-6 py-8 text-center text-gray-500">
                    Cargando URLs...
                  </td>
                </tr>
              ) : urls.length === 0 ? (
                <tr>
                  <td colSpan={columns.length + 1} className="px-6 py-8 text-center text-gray-500">
                    No se encontraron URLs externas registradas.
                  </td>
                </tr>
              ) : (
                urls.map((url) => {
                  const fechaFin = url.fecha_fin ? new Date(url.fecha_fin).toLocaleDateString('es-ES') : '—';
                  const fechaInicio = url.fecha_inicio ? new Date(url.fecha_inicio).toLocaleDateString('es-ES') : '—';
                  const urlCompleta = `${window.location.origin}/externo/${url.token_acceso}`;
                  const estaExpirada = url.fecha_fin && new Date(url.fecha_fin) < new Date();

                  return (
                    <tr key={url.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 text-sm text-gray-900 font-mono">
                        <a href={urlCompleta} target="_blank" rel="noopener noreferrer" className="hover:underline">
                          /externo/{url.token_acceso}
                        </a>
                        {estaExpirada && (
                          <span className="ml-2 text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">Expirada</span>
                                                    )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">{url.nombre || '—'}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">{fechaInicio}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">{fechaFin}</td>
                      <td className="px-6 py-4 text-center">
                        <button
                          onClick={() => handleAlternarEstado(url)}
                          className={`inline-flex items-center justify-center w-8 h-8 rounded-full transition-all duration-200 ${
                            url.activo_manual
                              ? 'bg-green-100 text-green-600 hover:bg-green-200'
                              : 'bg-red-100 text-red-600 hover:bg-red-200'
                          }`}
                          title={url.activo_manual ? 'Desactivar URL' : 'Activar URL'}
                        >
                          {url.activo_manual ? 'ON' : 'OFF'}
                        </button>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <button
                            onClick={() => handleEdit(url)}
                            className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                            title="Editar"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(url)}
                            className="p-1.5 text-red-600 hover:bg-red-50 rounded-md transition-colors"
                            title="Eliminar"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                          <a
                            href={urlCompleta}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 text-green-600 hover:bg-green-50 rounded-md transition-colors"
                            title="Ver URL pública"
                          >
                            <Link className="w-4 h-4" />
                          </a>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Paginación simple */}
        {totalItems > pageSize && (
          <div className="px-6 py-3 border-t border-gray-200 flex items-center justify-between">
            <div className="text-sm text-gray-600">
              Página {currentPage} de {Math.ceil(totalItems / pageSize)}
            </div>
            <div className="flex gap-1">
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  currentPage === 1
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
              >
                Anterior
              </button>
              <button
                onClick={() => setCurrentPage((p) => p + 1)}
                disabled={currentPage * pageSize >= totalItems}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  currentPage * pageSize >= totalItems
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
              >
                Siguiente
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modal */}
      <UrlExternaModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSave={handleSave}
        url={editingUrl}
      />
    </div>
  );
}
