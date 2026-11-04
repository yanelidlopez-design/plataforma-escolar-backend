import { useEffect, useState } from 'react';
import { BarChart3, FileDown } from 'lucide-react';
import axiosInstance from '../api/axiosInstance';
import { exportarEstadisticaMensualPDF } from '../api/asistencias';
import { downloadFile } from '../utils/downloadFile';

const mesActual = () => {
  const hoy = new Date();
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`;
};

const obtenerRangoCorte = (mesReporte) => {
  if (!mesReporte) return '';
  const [year, month] = mesReporte.split('-').map(Number);
  const inicio = new Date(year, month - 2, 26);
  const fin = new Date(year, month - 1, 25);
  const formato = new Intl.DateTimeFormat('es-VE', {
    day: 'numeric',
    month: 'long',
  });
  return `${formato.format(inicio)} al ${formato.format(fin)} de ${year}`;
};

export default function Reportes() {
  const [grados, setGrados] = useState([]);
  const [secciones, setSecciones] = useState([]);
  const [filtros, setFiltros] = useState({
    mes: mesActual(),
    grado: '',
    seccion: '',
  });
  const [cargandoCatalogos, setCargandoCatalogos] = useState(true);
  const [generando, setGenerando] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const cargarCatalogos = async () => {
      try {
        const [gradosResp, seccionesResp] = await Promise.all([
          axiosInstance.get('/core/grados/'),
          axiosInstance.get('/core/secciones/'),
        ]);
        setGrados(gradosResp.data.results || gradosResp.data || []);
        setSecciones(seccionesResp.data.results || seccionesResp.data || []);
      } catch (catalogError) {
        console.error('Error al cargar grados y secciones para reportes:', catalogError);
        setError('No se pudieron cargar los grados y secciones.');
      } finally {
        setCargandoCatalogos(false);
      }
    };

    cargarCatalogos();
  }, []);

  const handleGenerarEstadistica = async () => {
    if (!filtros.mes || !filtros.grado || !filtros.seccion) return;
    setGenerando(true);
    setError('');
    try {
      const gruposResp = await axiosInstance.get('/academico/grupos/', {
        params: { grado: filtros.grado, seccion: filtros.seccion },
      });
      const grupos = gruposResp.data.results || gruposResp.data || [];
      const grupo = grupos.find((item) => (
        Number(item.grado) === Number(filtros.grado)
        && Number(item.seccion) === Number(filtros.seccion)
        && item.periodo_detalle?.activo
      ));

      if (!grupo) {
        setError('No existe un grupo activo para el grado y sección seleccionados.');
        return;
      }

      const [year, month] = filtros.mes.split('-').map(Number);
      const response = await exportarEstadisticaMensualPDF({
        grupo_id: grupo.id_grupo,
        year,
        month,
      });
      await downloadFile(
        response,
        `estadistica_asistencia_${year}_${String(month).padStart(2, '0')}.pdf`,
      );
    } catch (reportError) {
      console.error('Error al generar la estadística mensual de asistencia:', reportError);
      let mensaje = reportError.message || 'No se pudo generar la estadística mensual.';
      if (reportError.response?.data instanceof Blob) {
        try {
          const detalle = JSON.parse(await reportError.response.data.text());
          mensaje = detalle.detail || detalle.error || mensaje;
        } catch (parseError) {
          console.error('No se pudo leer el error devuelto al generar el reporte:', parseError);
        }
      } else {
        mensaje = reportError.response?.data?.detail || mensaje;
      }
      setError(mensaje);
    } finally {
      setGenerando(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
          <BarChart3 className="h-6 w-6" /> Reportes
        </h1>
        <p className="text-sm text-gray-500">Exportación e informes del plantel.</p>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="rounded-xl border border-gray-200 bg-white p-6">
        <div className="mb-5">
          <h2 className="text-lg font-semibold text-gray-900">Estadística mensual de asistencia</h2>
          <p className="mt-1 text-sm text-gray-500">
            Genera el resumen por grado y sección del 26 del mes anterior al 25 del mes seleccionado.
            {filtros.mes && (
              <span className="mt-1 block font-medium text-gray-700">
                Período seleccionado: {obtenerRangoCorte(filtros.mes)}
              </span>
            )}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label htmlFor="reporte-mes" className="mb-1 block text-xs font-medium text-gray-700">
              Mes del reporte
            </label>
            <input
              id="reporte-mes"
              type="month"
              value={filtros.mes}
              onChange={(event) => setFiltros({ ...filtros, mes: event.target.value })}
              className="input-field"
            />
          </div>
          <div>
            <label htmlFor="reporte-grado" className="mb-1 block text-xs font-medium text-gray-700">
              Grado
            </label>
            <select
              id="reporte-grado"
              value={filtros.grado}
              onChange={(event) => setFiltros({
                ...filtros,
                grado: event.target.value,
                seccion: '',
              })}
              className="select-field"
              disabled={cargandoCatalogos}
            >
              <option value="">Selecciona un grado</option>
              {grados.map((grado) => (
                <option key={grado.id_grado} value={grado.id_grado}>
                  {grado.nombre_grado}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="reporte-seccion" className="mb-1 block text-xs font-medium text-gray-700">
              Sección
            </label>
            <select
              id="reporte-seccion"
              value={filtros.seccion}
              onChange={(event) => setFiltros({ ...filtros, seccion: event.target.value })}
              className="select-field"
              disabled={cargandoCatalogos}
            >
              <option value="">Selecciona una sección</option>
              {secciones.map((seccion) => (
                <option key={seccion.id_seccion} value={seccion.id_seccion}>
                  {seccion.nombre_seccion}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <button
            type="button"
            onClick={handleGenerarEstadistica}
            disabled={
              cargandoCatalogos
              || generando
              || !filtros.mes
              || !filtros.grado
              || !filtros.seccion
            }
            className="btn-primary flex items-center gap-2"
          >
            <FileDown className="h-4 w-4" />
            {generando ? 'Generando reporte...' : 'Descargar PDF'}
          </button>
        </div>
      </section>
    </div>
  );
}