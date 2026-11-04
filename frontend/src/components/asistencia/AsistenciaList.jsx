import { useState, useEffect } from 'react';
import { Calendar, Save, RotateCcw } from 'lucide-react';
import DataTable from '../common/DataTable';
import ExportButtons from '../common/ExportButtons';
import {
  getAsistencias,
  createAsistencia,
  updateAsistencia,
  exportarAsistenciasCSV,
  exportarAsistenciasExcel,
  exportarAsistenciasPDF,
} from '../../api/asistencias';
import axiosInstance from '../../api/axiosInstance';

const ESTADO_ASISTENCIA = [
  { value: 'P', label: 'Presente', color: 'bg-green-100 text-green-700 border-green-200' },
  { value: 'A', label: 'Ausente', color: 'bg-red-100 text-red-700 border-red-200' },
  { value: 'J', label: 'Justificado', color: 'bg-yellow-100 text-yellow-700 border-yellow-200' },
];

/**
 * AsistenciaList - Control de asistencia por fecha, grado y sección.
 * Permite marcar rápidamente Presente, Ausente o Justificado para cada alumno.
 */
export default function AsistenciaList() {
  const [filtros, setFiltros] = useState({
    fecha: new Date().toISOString().split('T')[0],
    id_grado: '',
    id_seccion: '',
  });
  const [alumnos, setAlumnos] = useState([]);
  const [asistencias, setAsistencias] = useState({}); // id_alumno -> estado
  const [registros, setRegistros] = useState({}); // id_alumno -> id_asistencia
  const [grados, setGrados] = useState([]);
  const [secciones, setSecciones] = useState([]);
  const [grupoId, setGrupoId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const filtrosCompletos = Boolean(filtros.fecha && filtros.id_grado && filtros.id_seccion);

  // Cargar grados y secciones para los filtros
  useEffect(() => {
    const cargarCatalogo = async () => {
      try {
        const [gResp, sResp] = await Promise.all([
          axiosInstance.get('/core/grados/'),
          axiosInstance.get('/core/secciones/'),
        ]);
        setGrados(gResp.data.results || gResp.data || []);
        setSecciones(sResp.data.results || sResp.data || []);
      } catch (error) {
        console.error('Error al cargar catálogos:', error);
      }
    };
    cargarCatalogo();
  }, []);

  // Cargar alumnos y asistencias según filtros
  const cargarAsistencias = async () => {
    setLoading(true);
    try {
      setError('');
      const params = {
        fecha: filtros.fecha,
        grado: filtros.id_grado,
        seccion: filtros.id_seccion,
      };
      const [alumnosResp, gruposResp] = await Promise.all([
        axiosInstance.get('/academico/alumnos/', { params }),
        axiosInstance.get('/academico/grupos/', {
          params: { grado: filtros.id_grado, seccion: filtros.id_seccion },
        }),
      ]);

      const listaAlumnos = alumnosResp.data.results || alumnosResp.data || [];
      const grupos = gruposResp.data.results || gruposResp.data || [];
      const grupo = grupos.find((item) => (
        Number(item.grado) === Number(filtros.id_grado)
        && Number(item.seccion) === Number(filtros.id_seccion)
        && item.periodo_detalle?.activo
      ));
      if (!grupo) {
        setAlumnos([]);
        setAsistencias({});
        setRegistros({});
        setGrupoId(null);
        setError('No existe un grupo activo para el grado y sección seleccionados.');
        return;
      }

      const asistenciasResp = await getAsistencias({
        fecha: filtros.fecha,
        grupo: grupo.id_grupo,
      });
      const listaAsistencias = asistenciasResp.data.results || asistenciasResp.data || [];

      // Indexar asistencias por id_alumno
      const asistenciasIndex = Object.fromEntries(
        listaAlumnos.map((alumno) => [alumno.id_alumno, 'P']),
      );
      const registrosIndex = {};
      listaAsistencias.forEach((a) => {
        const alumnoId = a.alumno || a.id_alumno;
        asistenciasIndex[alumnoId] = a.estado;
        registrosIndex[alumnoId] = a.id_asistencia;
      });

      setAlumnos(listaAlumnos);
      setAsistencias(asistenciasIndex);
      setRegistros(registrosIndex);
      setGrupoId(grupo.id_grupo);
    } catch (error) {
      console.error('Error al cargar asistencias:', error);
      setAlumnos([]);
      setAsistencias({});
      setRegistros({});
      setGrupoId(null);
      setError('No se pudieron cargar los datos de asistencia.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (filtrosCompletos) {
      cargarAsistencias();
    } else {
      setAlumnos([]);
      setAsistencias({});
      setRegistros({});
      setGrupoId(null);
    }
  }, [filtros, filtrosCompletos]);

  const handleCambiarEstado = (idAlumno, estado) => {
    setAsistencias((prev) => ({ ...prev, [idAlumno]: estado }));
  };

  const handleAplicarRapido = (estado) => {
    const nuevo = {};
    alumnos.forEach((a) => {
      nuevo[a.id_alumno] = estado;
    });
    setAsistencias(nuevo);
  };

  const handleGuardar = async () => {
    if (!grupoId || !filtrosCompletos) return;
    setSaving(true);
    setError('');
    try {
      const promises = Object.entries(asistencias).map(([idAlumno, estado]) => {
        const alumno = alumnos.find((a) => String(a.id_alumno) === String(idAlumno));
        if (!alumno) return null;
        const data = {
          alumno: parseInt(idAlumno, 10),
          grupo: grupoId,
          fecha: filtros.fecha,
          estado,
        };
        const registroId = registros[idAlumno];
        return registroId
          ? updateAsistencia(registroId, data)
          : createAsistencia(data);
      });
      await Promise.all(promises.filter(Boolean));
      alert('Asistencia guardada exitosamente.');
      cargarAsistencias();
    } catch (error) {
      console.error('Error al guardar asistencia:', error);
      const detalle = error.response?.data?.detail;
      setError(
        typeof detalle === 'string'
          ? detalle
          : detalle
            ? JSON.stringify(detalle)
            : 'No se pudo guardar la asistencia. Verifica tu sesión e inténtalo de nuevo.',
      );
    } finally {
      setSaving(false);
    }
  };

  const handleExportar = (format) => {
    const params = { fecha: filtros.fecha, grupo: grupoId };
    if (format === 'csv') exportarAsistenciasCSV(params);
    if (format === 'excel') exportarAsistenciasExcel(params);
    if (format === 'pdf') exportarAsistenciasPDF(params);
  };

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Calendar className="w-5 h-5" /> Asistencia
          </h2>
          <p className="text-sm text-gray-500">
            Registro de asistencia por fecha, grado y sección.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={cargarAsistencias}
            disabled={loading || !filtrosCompletos}
            className="btn-secondary flex items-center gap-2"
          >
            <RotateCcw className="w-4 h-4" /> Actualizar
          </button>
          <button
            onClick={handleGuardar}
            disabled={saving || loading || !grupoId || alumnos.length === 0}
            className="btn-primary flex items-center gap-2"
          >
            <Save className="w-4 h-4" /> Guardar Asistencia
          </button>
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Filtros */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Fecha</label>
            <input
              type="date"
              value={filtros.fecha}
              onChange={(e) => setFiltros({ ...filtros, fecha: e.target.value })}
              className="input-field"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Grado</label>
            <select
              value={filtros.id_grado}
              onChange={(e) =>
                setFiltros({ ...filtros, id_grado: e.target.value, id_seccion: '' })
              }
              className="select-field"
            >
              <option value="">Todos los grados</option>
              {grados.map((g) => (
                <option key={g.id_grado} value={g.id_grado}>
                  {g.nombre_grado}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Sección</label>
            <select
              value={filtros.id_seccion}
              onChange={(e) => setFiltros({ ...filtros, id_seccion: e.target.value })}
              className="select-field"
            >
              <option value="">Todas las secciones</option>
              {secciones.map((s) => (
                <option key={s.id_seccion} value={s.id_seccion}>
                  {s.nombre_seccion}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Selectores rápidos */}
        <div className="mt-4 flex items-center gap-3">
          <span className="text-xs font-medium text-gray-600">Aplicar a todos:</span>
          {ESTADO_ASISTENCIA.map((e) => (
            <button
              key={e.value}
              onClick={() => handleAplicarRapido(e.value)}
              disabled={!filtrosCompletos || alumnos.length === 0}
              className={`px-3 py-1.5 text-xs font-medium rounded-md border transition-colors ${
                e.color
              } hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-50`}
            >
              {e.label}
            </button>
          ))}
        </div>
      </div>

      {/* Listado de alumnos con selectores de asistencia */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">
            Alumnos ({alumnos.length})
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
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Cédula</th>
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Nombre Completo</th>
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Grado</th>
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Sección</th>
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase text-center">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                    Cargando alumnos...
                  </td>
                </tr>
              ) : !filtrosCompletos ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                    Selecciona fecha, grado y sección para cargar la lista de alumnos.
                  </td>
                </tr>
              ) : alumnos.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                    No se encontraron alumnos para los filtros seleccionados.
                  </td>
                </tr>
              ) : (
                alumnos.map((alumno) => {
                  const estadoActual = asistencias[alumno.id_alumno] || 'P';
                  const estadoConfig = ESTADO_ASISTENCIA.find(
                    (e) => e.value === estadoActual
                  ) || ESTADO_ASISTENCIA[0];
                  const nombreCompleto = [
                    alumno.primer_nombre,
                    alumno.segundo_nombre,
                    alumno.primer_apellido,
                    alumno.segundo_apellido,
                  ]
                    .filter(Boolean)
                    .join(' ');

                  return (
                    <tr
                      key={alumno.id_alumno}
                      className="hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {alumno.numero_documento_identidad || alumno.cedula_escolar || '—'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">{nombreCompleto}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {alumno.grado_actual || '—'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {alumno.seccion_actual || '—'}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div className="flex items-center justify-center gap-2">
                          {ESTADO_ASISTENCIA.map((e) => (
                            <button
                              key={e.value}
                              onClick={() => handleCambiarEstado(alumno.id_alumno, e.value)}
                              className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border transition-all duration-200 ${
                                estadoActual === e.value
                                  ? `${e.color} shadow-sm`
                                  : 'bg-white text-gray-400 border-gray-300 hover:bg-gray-50'
                              }`}
                            >
                              {e.label.charAt(0)}
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
