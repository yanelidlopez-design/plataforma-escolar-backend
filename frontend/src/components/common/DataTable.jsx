import { useState } from 'react';
import { Search, Edit, Eye, Trash2 } from 'lucide-react';
import ExportButtons from './ExportButtons';
import Pagination from './Pagination';

/**
 * DataTable - Tabla reutilizable con búsqueda, exportación, acciones y paginación.
 * Diseño limpio estilo referencia: encabezados gris claro, filas con hover,
 * columna de acciones con íconos.
 *
 * Props:
 *  - columns: [{ key, label, render?(row) }]
 *  - data: array de filas
 *  - totalItems: número total de elementos (para paginación)
 *  - currentPage: página actual
 *  - pageSize: elementos por página
 *  - onSearch: (query) => void
 *  - onExportExcel, onExportPdf, onExportCsv: funciones de exportación
 *  - onEdit, onView, onDelete: funciones de acción por fila
 *  - loading: estado de carga
 */
export default function DataTable({
  columns,
  data,
  totalItems,
  currentPage,
  pageSize,
  onSearch,
  onPageChange,
  onExportExcel,
  onExportPdf,
  onExportCsv,
  onEdit,
  onView,
  onDelete,
  loading = false,
  primaryActionLabel = '+ Registrar',
}) {
  const [searchQuery, setSearchQuery] = useState('');

  const visibleData = data.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );
  const resultCount = totalItems;

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Encabezado: búsqueda + exportación + acción principal */}
      <div className="px-6 py-4 border-b border-gray-200 flex flex-col md:flex-row md:items-center gap-4">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                if (onSearch) onSearch(e.target.value);
              }}
              placeholder="Buscar por nombre, cédula o ID..."
              className="input-field pl-10"
            />
          </div>
        </div>

        <div className="flex gap-2">
          <ExportButtons
            onExportExcel={onExportExcel}
            onExportPdf={onExportPdf}
            onExportCsv={onExportCsv}
          />
        </div>
      </div>

      {/* Contenedor de la tabla */}
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
              <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Acciones
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan={columns.length + 1} className="px-6 py-8 text-center text-gray-500">
                  Cargando...
                </td>
              </tr>
            ) : visibleData.length === 0 ? (
              <tr>
                <td colSpan={columns.length + 1} className="px-6 py-8 text-center text-gray-500">
                  No se encontraron resultados.
                </td>
              </tr>
            ) : (
              visibleData.map((row) => (
                <tr key={row.id || row.id_alumno || row.id_profesor} className="hover:bg-gray-50 transition-colors">
                  {columns.map((col) => (
                    <td key={col.key} className="px-6 py-4 text-sm text-gray-900">
                      {col.render ? col.render(row) : row[col.key]}
                    </td>
                  ))}
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      {onView && (
                        <button
                          onClick={() => onView(row)}
                          className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                          title="Ver"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      )}
                      {onEdit && (
                        <button
                          onClick={() => onEdit(row)}
                          className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                          title="Editar"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                      )}
                      {onDelete && (
                        <button
                          onClick={() => onDelete(row)}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded-md transition-colors"
                          title="Eliminar"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Paginación inferior */}
      <Pagination
        currentPage={currentPage}
        totalPages={Math.ceil(resultCount / pageSize)}
        onPageChange={onPageChange}
        pageSize={pageSize}
        totalItems={resultCount}
      />
    </div>
  );
}