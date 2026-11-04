import { useState, useEffect } from 'react';
import {
  FileDown,
  FileSpreadsheet,
  FileText,
  GraduationCap,
  Save,
  RotateCcw,
  Plus,
  Trash2,
} from 'lucide-react';
import { downloadFile } from '../../utils/downloadFile';
import {
  getEvaluacionesCualitativas,
  guardarEvaluacionesCualitativas,
  crearCriterioCualitativo,
  retirarCriterioCualitativo,
  exportarBoletaCualitativa,
} from '../../api/calificaciones';
import axiosInstance from '../../api/axiosInstance';

const INDICADORES_CUALITATIVOS = [
  { codigo: 'L', nombre: 'Logrado' },
  { codigo: 'PM', nombre: 'Por mejorar' },
  { codigo: 'PL', nombre: 'Plenamente logrado' },
  { codigo: 'EP', nombre: 'En proceso' },
  { codigo: 'I', nombre: 'Inicio' },
];

/**
 * CalificacionesList - Carga de notas por periodo/lapso.
 * Tabla de evaluaciones cualitativas por alumno y criterio.
 */
export default function CalificacionesList() {
  const [filtros, setFiltros] = useState({
    id_periodo: '',
    id_grado: '',
    id_seccion: '',
  });
  const [periodos, setPeriodos] = useState([]);
  const [grados, setGrados] = useState([]);
  const [secciones, setSecciones] = useState([]);
  const [criterios, setCriterios] = useState([]);
  const [alumnos, setAlumnos] = useState([]);
  const [notas, setNotas] = useState({});
  const [nivelEducativo, setNivelEducativo] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savingCriterio, setSavingCriterio] = useState(false);
  const [nuevoCriterio, setNuevoCriterio] = useState('');
  const [descargasBoleta, setDescargasBoleta] = useState({});

  // Cargar catálogos para seleccionar el período y el grupo.
  useEffect(() => {
    const cargarCatalogo = async () => {
      try {
        const [pResp, gResp, sResp] = await Promise.all([
          axiosInstance.get('/academico/periodos-calificacion/'),
          axiosInstance.get('/core/grados/'),
          axiosInstance.get('/core/secciones/'),
        ]);
        setPeriodos(pResp.data.results || pResp.data || []);
        setGrados(gResp.data.results || gResp.data || []);
        setSecciones(sResp.data.results || sResp.data || []);
      } catch (error) {
        console.error('Error al cargar catálogos:', error);
      }
    };
    cargarCatalogo();
  }, []);

  // Cargar alumnos y notas según filtros
  const cargarCalificaciones = async () => {
    if (!filtros.id_periodo || !filtros.id_grado || !filtros.id_seccion) {
      setAlumnos([]);
      setNotas({});
      setCriterios([]);
      setNivelEducativo('');
      setError('');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const params = {
        id_periodo: filtros.id_periodo,
        id_grado: filtros.id_grado,
        id_seccion: filtros.id_seccion,
      };
      const { data } = await getEvaluacionesCualitativas(params);
      const notasIndex = {};
      data.alumnos.forEach((alumno) => {
        alumno.evaluaciones.forEach((evaluacion) => {
          notasIndex[`${alumno.id_alumno}-${evaluacion.id_criterio}`] = {
            indicador: evaluacion.indicador,
            sugerencias: evaluacion.sugerencias,
          };
        });
      });

      setNivelEducativo(data.nivel_educativo);
      setCriterios(data.criterios);
      setAlumnos(data.alumnos);
      setNotas(notasIndex);
    } catch (error) {
      console.error('Error al cargar calificaciones:', error);
      setAlumnos([]);
      setNotas({});
      setCriterios([]);
      setNivelEducativo('');
      setError(error.response?.data?.detail || 'No se pudieron cargar las calificaciones.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargarCalificaciones();
  }, [filtros]);

  const handleCambiarNota = (idAlumno, idCriterio, valor) => {
    const clave = `${idAlumno}-${idCriterio}`;
    setNotas((prev) => ({ ...prev, [clave]: valor }));
  };

  const handleGuardar = async () => {
    setSaving(true);
    setError('');
    try {
      const alumnosEvaluaciones = alumnos.map((alumno) => ({
        id_alumno: alumno.id_alumno,
        evaluaciones: criterios
          .map((criterio) => ({
            id_criterio: criterio.id,
            indicador: notas[`${alumno.id_alumno}-${criterio.id}`]?.indicador,
            sugerencias: notas[`${alumno.id_alumno}-${criterio.id}`]?.sugerencias,
          }))
          .filter((evaluacion) => evaluacion.indicador || evaluacion.sugerencias?.trim()),
      }));
      await guardarEvaluacionesCualitativas({
        id_periodo: Number(filtros.id_periodo),
        id_grado: Number(filtros.id_grado),
        id_seccion: Number(filtros.id_seccion),
        alumnos_evaluaciones: alumnosEvaluaciones,
      });
      alert('Calificaciones y sugerencias guardadas exitosamente.');
      cargarCalificaciones();
    } catch (error) {
      console.error('Error al guardar calificaciones:', error);
      setError(error.response?.data?.detail || 'No se pudieron guardar las calificaciones.');
    } finally {
      setSaving(false);
    }
  };

  const handleAgregarCriterio = async (event) => {
    event.preventDefault();
    setSavingCriterio(true);
    setError('');
    try {
      await crearCriterioCualitativo({
        descripcion_criterio: nuevoCriterio,
        ...filtros,
      });
      setNuevoCriterio('');
      await cargarCalificaciones();
    } catch (error) {
      setError(error.response?.data?.detail || 'No se pudo agregar el criterio.');
    } finally {
      setSavingCriterio(false);
    }
  };

  const handleRetirarCriterio = async (criterio) => {
    if (!window.confirm(`¿Retirar "${criterio.descripcion_criterio}" de este período?`)) {
      return;
    }
    setError('');
    try {
      await retirarCriterioCualitativo({
        ...filtros,
        id_criterio: criterio.id,
      });
      await cargarCalificaciones();
    } catch (error) {
      setError(error.response?.data?.detail || 'No se pudo retirar el criterio.');
    }
  };

  const handleDescargarBoleta = async (alumno, formato) => {
    const clave = `${alumno.id_alumno}-${formato}`;
    setDescargasBoleta((prev) => ({ ...prev, [clave]: true }));
    setError('');
    try {
      const response = await exportarBoletaCualitativa(
        formato,
        alumno.id_alumno,
        filtros.id_periodo,
      );
      await downloadFile(
        response,
        `boleta_${alumno.id_alumno}.${formato === 'excel' ? 'xlsx' : 'pdf'}`,
      );
    } catch (exportError) {
      console.error(`Error al exportar boleta ${formato}:`, exportError);
      let mensaje = exportError.message || 'No se pudo descargar la boleta.';
      if (exportError.response?.data instanceof Blob) {
        try {
          const detalle = JSON.parse(await exportError.response.data.text());
          mensaje = detalle.detail || detalle.error || mensaje;
        } catch (parseError) {
          console.error('No se pudo leer el error devuelto por la exportación:', parseError);
        }
      } else {
        mensaje = exportError.response?.data?.detail || mensaje;
      }
      setError(mensaje);
    } finally {
      setDescargasBoleta((prev) => ({ ...prev, [clave]: false }));
    }
  };

  const filtrosCompletos = Boolean(
    filtros.id_periodo && filtros.id_grado && filtros.id_seccion,
  );
  const tieneDatosParaGuardar = Object.values(notas).some(
    (nota) => nota.indicador || nota.sugerencias?.trim(),
  );
  const administradorCriterios = filtrosCompletos && nivelEducativo !== 'INICIAL' ? (
    <section className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">Criterios de este período y sección</h3>
        <p className="text-xs text-gray-500 mt-1">
          Los criterios se configuran por grado, sección y lapso. Los ya calificados no se pueden retirar.
        </p>
      </div>
      {criterios.length > 0 && (
        <ul className="divide-y divide-gray-100 border border-gray-100 rounded-lg">
          {criterios.map((criterio) => (
            <li key={criterio.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <span className="text-sm text-gray-700">{criterio.descripcion_criterio}</span>
              <button
                type="button"
                onClick={() => handleRetirarCriterio(criterio)}
                className="text-red-600 hover:text-red-800"
                aria-label={`Retirar criterio ${criterio.descripcion_criterio} de este período`}
                title="Retirar de este período"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={handleAgregarCriterio} className="flex flex-col md:flex-row gap-3">
        <input
          required
          maxLength={255}
          value={nuevoCriterio}
          onChange={(event) => setNuevoCriterio(event.target.value)}
          placeholder="Descripción del criterio"
          aria-label="Descripción del criterio"
          className="input-field md:flex-1"
        />
        <button
          type="submit"
          disabled={savingCriterio || loading}
          className="btn-secondary flex items-center justify-center gap-2"
        >
          <Plus className="w-4 h-4" /> Agregar criterio
        </button>
      </form>
    </section>
  ) : null;

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <GraduationCap className="w-5 h-5" /> Calificaciones
          </h2>
          <p className="text-sm text-gray-500">
            Carga de notas por periodo/lapso por alumno y criterio de evaluación.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={cargarCalificaciones}
            disabled={loading || !filtrosCompletos}
            className="btn-secondary flex items-center gap-2"
          >
            <RotateCcw className="w-4 h-4" /> Actualizar
          </button>
          <button
            onClick={handleGuardar}
            disabled={saving || loading || !tieneDatosParaGuardar || nivelEducativo === 'INICIAL'}
            className="btn-primary flex items-center gap-2"
          >
            <Save className="w-4 h-4" /> Guardar Notas
          </button>
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}
      {administradorCriterios}

      {/* Filtros */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Periodo / Lapso</label>
            <select
              value={filtros.id_periodo}
              onChange={(e) => setFiltros({ ...filtros, id_periodo: e.target.value })}
              className="select-field"
            >
              <option value="">Seleccionar periodo</option>
              {periodos.map((p) => (
                <option key={p.id_periodo || p.id} value={p.id_periodo || p.id}>
                  {p.nombre_periodo || p.codigo_periodo || `Periodo ${p.id_periodo || p.id}`}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Grado</label>
            <select
              value={filtros.id_grado}
              onChange={(e) => setFiltros({ ...filtros, id_grado: e.target.value, id_seccion: '' })}
              className="select-field"
            >
              <option value="">Seleccionar grado</option>
              {grados.map((g) => (
                <option key={g.id_grado} value={g.id_grado}>{g.nombre_grado}</option>
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
              <option value="">Seleccionar sección</option>
              {secciones.map((s) => (
                <option key={s.id_seccion} value={s.id_seccion}>{s.nombre_seccion}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {filtrosCompletos && nivelEducativo === 'INICIAL' ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
          Educación Inicial se registra mediante informes descriptivos, según la escala pedagógica configurada.
        </div>
      ) : filtrosCompletos && criterios.length > 0 ? (
      <>
      {/* Tabla estructurada de calificaciones */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">
            Registro de Notas ({alumnos.length} alumnos)
          </h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
              <tr>
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase w-48">Alumno</th>
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase text-center">Cédula</th>
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase text-center">Boleta</th>
                {criterios.map((criterio) => (
                  <th
                    key={criterio.id}
                    className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase text-center min-w-48"
                  >
                    {criterio.descripcion_criterio}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={criterios.length + 3} className="px-6 py-8 text-center text-gray-500">
                    Cargando alumnos y notas...
                  </td>
                </tr>
              ) : alumnos.length === 0 ? (
                <tr>
                  <td colSpan={criterios.length + 3} className="px-6 py-8 text-center text-gray-500">
                    No se encontraron alumnos para los filtros seleccionados.
                  </td>
                </tr>
              ) : (
                alumnos.map((alumno) => {
                  const nombreCompleto = [
                    alumno.primer_nombre,
                    alumno.segundo_nombre,
                    alumno.primer_apellido,
                    alumno.segundo_apellido,
                  ]
                    .filter(Boolean)
                    .join(' ');
                  const cedula = alumno.cedula_escolar || '—';

                  return (
                    <tr key={alumno.id_alumno} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 text-sm text-gray-900 font-medium">{nombreCompleto}</td>
                      <td className="px-6 py-4 text-sm text-gray-600 text-center">{cedula}</td>
                      <td className="px-4 py-4 text-center">
                        <div className="flex justify-center gap-2">
                          <button
                            type="button"
                            onClick={() => handleDescargarBoleta(alumno, 'pdf')}
                            disabled={descargasBoleta[`${alumno.id_alumno}-pdf`]}
                            className="rounded-md p-2 text-red-700 hover:bg-red-50 disabled:opacity-50"
                            title="Descargar boleta en PDF"
                            aria-label={`Descargar boleta PDF de ${nombreCompleto}`}
                          >
                            <FileDown className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDescargarBoleta(alumno, 'excel')}
                            disabled={descargasBoleta[`${alumno.id_alumno}-excel`]}
                            className="rounded-md p-2 text-green-700 hover:bg-green-50 disabled:opacity-50"
                            title="Descargar boleta en Excel"
                            aria-label={`Descargar boleta Excel de ${nombreCompleto}`}
                          >
                            <FileSpreadsheet className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                      {criterios.map((criterio) => (
                        <td
                          key={criterio.id}
                          className="px-4 py-4 text-center min-w-48"
                        >
                          <select
                            aria-label={`${criterio.descripcion_criterio} para ${nombreCompleto}`}
                            value={notas[`${alumno.id_alumno}-${criterio.id}`]?.indicador || ''}
                            onChange={(event) =>
                              handleCambiarNota(alumno.id_alumno, criterio.id, {
                                ...notas[`${alumno.id_alumno}-${criterio.id}`],
                                indicador: event.target.value,
                              })
                            }
                            className="select-field min-w-44"
                          >
                            <option value="">Seleccionar</option>
                            {INDICADORES_CUALITATIVOS.map((indicador) => (
                              <option key={indicador.codigo} value={indicador.codigo}>
                                {indicador.nombre}
                              </option>
                            ))}
                          </select>
                          <textarea
                            aria-label={`Sugerencia para ${criterio.descripcion_criterio} de ${nombreCompleto}`}
                            value={notas[`${alumno.id_alumno}-${criterio.id}`]?.sugerencias || ''}
                            onChange={(event) =>
                              handleCambiarNota(alumno.id_alumno, criterio.id, {
                                ...notas[`${alumno.id_alumno}-${criterio.id}`],
                                sugerencias: event.target.value,
                              })
                            }
                            placeholder="Sugerencia para la boleta"
                            rows={2}
                            maxLength={4000}
                            className="input-field mt-2 min-w-44 text-left text-xs"
                          />
                        </td>
                      ))}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Nota informativa */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <FileText className="w-4 h-4 text-blue-600 mt-0.5" />
          <div className="text-sm text-blue-800">
            <p className="font-medium">Escala de calificación cualitativa:</p>
            <p className="text-blue-700">
              {INDICADORES_CUALITATIVOS.map((indicador) => `${indicador.nombre} (${indicador.codigo})`).join(' | ')}.
            </p>
          </div>
        </div>
        </div>
        </>
        ) : filtrosCompletos ? (
          <div className="bg-white border border-gray-200 rounded-xl p-6 text-center text-sm text-gray-500">
            No hay criterios de evaluación configurados para esta sección.
          </div>
        ) : null}
    </div>
  );
}
