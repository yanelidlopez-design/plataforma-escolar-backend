import { ChevronLeft, ChevronRight } from 'lucide-react';

/**
 * Pagination - Control de paginación inferior.
 * Permite navegar entre páginas con anterior/siguiente y número de página.
 */
export default function Pagination({
  currentPage,
  totalPages,
  onPageChange,
  pageSize,
  totalItems,
}) {
  if (totalPages <= 1) return null;

  const pagesToShow = 3;
  const startPage = Math.max(1, currentPage - Math.floor(pagesToShow / 2));
  const endPage = Math.min(totalPages, startPage + pagesToShow - 1);

  return (
    <nav className="flex items-center justify-between px-4 py-3 bg-white border-t border-gray-200 rounded-b-lg">
      <div className="text-sm text-gray-600">
        Mostrando <strong>{((currentPage - 1) * pageSize) + 1}</strong> a{' '}
        <strong>{Math.min(currentPage * pageSize, totalItems)}</strong> de{' '}
        <strong>{totalItems}</strong> resultados
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
            currentPage === 1
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {[...Array(endPage - startPage + 1)].map((_, i) => {
          const page = startPage + i;
          return (
            <button
              key={page}
              onClick={() => onPageChange(page)}
              className={`w-8 h-8 text-sm rounded-lg transition-colors flex items-center justify-center ${
                page === currentPage
                  ? 'bg-primary-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
              }`}
            >
              {page}
            </button>
          );
        })}

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
            currentPage === totalPages
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </nav>
  );
}