import { FileText, FileSpreadsheet, FileCode } from 'lucide-react';

/**
 * ExportButtons - Botones de exportación con iconos para Excel, PDF y CSV.
 */
export default function ExportButtons({ onExportExcel, onExportPdf, onExportCsv }) {
  return (
    <div className="flex gap-2">
      <button
        onClick={onExportExcel}
        className="btn-secondary flex items-center gap-2"
        title="Exportar a Excel"
      >
        <FileSpreadsheet className="w-4 h-4" />
        <span className="hidden sm:inline">Excel</span>
      </button>
      <button
        onClick={onExportPdf}
        className="btn-secondary flex items-center gap-2"
        title="Exportar a PDF"
      >
        <FileText className="w-4 h-4" />
        <span className="hidden sm:inline">PDF</span>
      </button>
      <button
        onClick={onExportCsv}
        className="btn-secondary flex items-center gap-2"
        title="Exportar a CSV"
      >
        <FileCode className="w-4 h-4" />
        <span className="hidden sm:inline">CSV</span>
      </button>
    </div>
  );
}