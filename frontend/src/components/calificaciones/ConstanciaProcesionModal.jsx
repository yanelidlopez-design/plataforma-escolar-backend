import { useState, useEffect } from 'react';
import {
  Save, FileDown, Info, Globe, Mail, Clock, AlertCircle, CheckCircle2,
} from 'lucide-react';
import Modal from '../common/Modal';
import {
  getConfiguracionInstitucional,
  guardarConfiguracionInstitucional,
  actualizarConfiguracionInstitucional,
  getConstanciaProsecucionAlumno,
  guardarConstanciaProsecucionAlumno,
  descargarConstanciaProcesionPDF,
} from '../../api/prosecucion';

const GRADOS_CURSADO = [
  { valor: 'Primer', label: 'Primer Grado' },
  { valor: 'Segundo', label: 'Segundo Grado' },
  { valor: 'Tercer', label: 'Tercer Grado' },
  { valor: 'Cuarto', label: 'Cuarto Grado' },
  { valor: 'Quinto', label: 'Quinto Grado' },
];

const GRADOS_PROMOVIDO = [
  { valor: 'Segundo', label: 'Segundo Grado' },
  { valor: 'Tercer', label: 'Tercer Grado' },
  { valor: 'Cuarto', label: 'Cuarto Grado' },
  { valor: 'Quinto', label: 'Quinto Grado' },
  { valor: 'Sexto', label: 'Sexto Grado' },
];

const LITERALES = ['A', 'B', 'C', 'D', 'E'];

export default function ConstanciaProcesionModal({
  isOpen,
  onClose,
  alumno,
  onConstanciaGuardada,
}) {
  const [constanciaData, setConstanciaData] = useState({
    periodo_escolar: '',
    grado_cursado: '',
    literal_final: '',
    promovido_al_grado: '',
    lugar_expedicion: '',
    fecha_expedicion: new Date().toISOString().split('T')[0],
  });
  const [configuracion, setConfiguracion] = useState({
    nombre_institucion: '',
    municipio: '',
    parroquia: '',
    cdce_estadal: '',
    director_institucion_nombre: '',
    director_institucion_cedula: '',
    director_cdce_nombre: '',
    director_cdce_cedula: '',
  });
  const [cargando, setCargando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [error, setError] = useState('');
  const [existeConstancia, setExisteConstancia] = useState(false);
  const [editandoConfig, setEditandoConfig] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setError('');
    if (alumno?.id_alumno) {
      cargarConstancia();
    }
    cargarConfiguracion();
  }, [isOpen, alumno]);

  const cargarConstancia = async () => {
    if (!alumno?.id_alumno) return;
    setCargando(true);
    try {
      const resp = await getConstanciaProsecucionAlumno(alumno.id_alumno, '');
      if (resp.data.success && resp.data.constancia) {
        setConstanciaData({
          periodo_escolar: resp.data.constancia.periodo_escolar || '',
          grado_cursado: resp.data.constancia.grado_cursado || '',
          literal_final: resp.data.constancia.literal_final || '',
          promovido_al_grado: resp.data.constancia.promovido_al_grado || '',
          lugar_expedicion: resp.data.constancia.lugar_expedicion || '',
          fecha_expedicion: resp.data.constancia.fecha_expedicion
            ? new Date(resp.data.constancia.fecha_expedicion).toISOString().split('T')[0]
            : new Date().toISOString().split('T')[0],
        });
        setExisteConstancia(true);
      } else {
        setExisteConstancia(false);
      }
    } catch (e) {
      setExisteConstancia(false);
    } finally {
      setCargando(false);
    }
  };

  const cargarConfiguracion = async () => {
    try {
      const resp = await getConfiguracionInstitucional();
      setConfiguracion(resp.data || {});
    } catch (e) {
      // Configuración no existe aún
    }
  };

  const handleGuardar = async () => {
    if (!alumno?.id_alumno) return;
    if (!constanciaData.periodo_escolar || !constanciaData.grado_cursado
      || !constanciaData.literal_final || !constanciaData.promovido_al_grado
      || !constanciaData.lugar_expedicion || !constanciaData.fecha_expedicion) {
      setError('Todos los campos son obligatorios.');
      return;
    }
    setGuardando(true);
    setError('');
    try {
      await guardarConstanciaProsecucionAlumno(alumno.id_alumno, {
        ...constanciaData,
      });
      setExisteConstancia(true);
      if (onConstanciaGuardada) {
        onConstanciaGuardada(alumno.id_alumno);
      }
      const d = new Date(constanciaData.fecha_expedicion);
      const meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
      setError(`Constancia guardada: ${constanciaData.lugar_expedicion}, ${d.getDate()} de ${meses[d.getMonth()]} de ${d.getFullYear()}.`);
    } catch (e) {
      setError(e.response?.data?.error || 'No se pudo guardar la constancia.');
    } finally {
      setGuardando(false);
    }
  };

  const handleGuardarConfiguracion = async () => {
    setGuardando(true);
    setError('');
    try {
      if (configuracion.id_configuracion) {
        await actualizarConfiguracionInstitucional(configuracion);
      } else {
        await guardarConfiguracionInstitucional(configuracion);
      }
      setEditandoConfig(false);
      setError('Datos institucionales guardados correctamente.');
    } catch (e) {
      setError(e.response?.data?.error || 'No se pudo guardar la configuración institucional.');
    } finally {
      setGuardando(false);
    }
  };

  const handleDescargarPDF = async () => {
    if (!alumno?.id_alumno) return;
    setDescargando(true);
    setError('');
    try {
      const response = await descargarConstanciaProcesionPDF(alumno.id_alumno);
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Constancia_Procesion_${alumno.cedula_escolar || alumno.id_alumno}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (e) {
      setError(e.response?.data?.error || 'No se pudo descargar el PDF.');
    } finally {
      setDescargando(false);
    }
  };

  if (!isOpen) return null;

  const nombreCompleto = [
    alumno?.primer_nombre, alumno?.segundo_nombre,
    alumno?.primer_apellido, alumno?.segundo_apellido,
  ].filter(Boolean).join(' ');

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        alumno
          ? `Constancia de Prosecución - ${nombreCompleto}`
          : 'Configuración Institucional / Prosecución'
      }
    >
      <div className="space-y-4 max-h-[70vh] overflow-y-auto">
        {alumno ? (
          <>
            <div className="border rounded-lg p-4 bg-gray-50">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Datos del Estudiante</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Nombre completo</label>
              <input type="text" value={nombreCompleto} readOnly className="w-full border p-1 rounded bg-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Cédula Escolar / Documento</label>
              <input type="text" value={alumno?.cedula_escolar || alumno?.numero_documento_identidad || ''} readOnly className="w-full border p-1 rounded bg-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Lugar de Nacimiento</label>
              <input type="text" value={alumno?.municipio_nacimiento || alumno?.lugar_nacimiento || ''} readOnly className="w-full border p-1 rounded bg-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Fecha de Nacimiento</label>
              <input type="text" value={alumno?.fecha_nacimiento || ''} readOnly className="w-full border p-1 rounded bg-white" />
            </div>
          </div>
        </div>
          </>
        ) : null}
        {alumno ? (
          <>
        <div className="border rounded-lg p-4 bg-white">
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-600" /> Datos de Procesión
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Grado Cursado</label>
              <select
                value={constanciaData.grado_cursado}
                onChange={(e) => setConstanciaData({ ...constanciaData, grado_cursado: e.target.value })}
                className="w-full border p-2 rounded text-sm"
              >
                <option value="">Seleccionar grado</option>
                {GRADOS_CURSADO.map((g) => (
                  <option key={g.valor} value={g.valor}>{g.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Literal</label>
              <select
                value={constanciaData.literal_final}
                onChange={(e) => setConstanciaData({ ...constanciaData, literal_final: e.target.value })}
                className="w-full border p-2 rounded text-sm"
              >
                <option value="">Seleccionar literal</option>
                {LITERALES.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Período Escolar</label>
              <input
                type="text"
                value={constanciaData.periodo_escolar}
                onChange={(e) => setConstanciaData({ ...constanciaData, periodo_escolar: e.target.value })}
                placeholder="Ej: 2025-2026"
                className="w-full border p-2 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Grado Promovido</label>
              <select
                value={constanciaData.promovido_al_grado}
                onChange={(e) => setConstanciaData({ ...constanciaData, promovido_al_grado: e.target.value })}
                className="w-full border p-2 rounded text-sm"
              >
                <option value="">Seleccionar grado</option>
                {GRADOS_PROMOVIDO.map((g) => (
                  <option key={g.valor} value={g.valor}>{g.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Lugar de Expedición</label>
              <input
                type="text"
                value={constanciaData.lugar_expedicion}
                onChange={(e) => setConstanciaData({ ...constanciaData, lugar_expedicion: e.target.value })}
                placeholder="Ej: Calabozo"
                className="w-full border p-2 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Fecha de Expedición</label>
              <input
                type="date"
                value={constanciaData.fecha_expedicion}
                onChange={(e) => setConstanciaData({ ...constanciaData, fecha_expedicion: e.target.value })}
                className="w-full border p-2 rounded text-sm"
              />
            </div>
          </div>
        </div>
          </>
        ) : null}
        {alumno ? (
          <>
        <div className="flex gap-3 justify-end">
          <button
            onClick={handleGuardar}
            disabled={guardando}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50 text-sm"
          >
            <Save className="w-4 h-4" /> Guardar Constancia
          </button>
          {existeConstancia && (
            <button
              onClick={handleDescargarPDF}
              disabled={descargando}
              className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 disabled:opacity-50 text-sm"
            >
              <FileDown className="w-4 h-4" /> Descargar PDF Individual
            </button>
          )}
        </div>
          </>
        ) : null}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <details className="border rounded-lg bg-gray-50">
          <summary className="cursor-pointer list-none p-3 font-medium text-gray-700 flex items-center gap-2">
            {editandoConfig ? '▼' : '▶'} Datos de la Institución y Directores
          </summary>
          <div className="p-4 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Nombre Institución</label>
                <input
                  value={configuracion.nombre_institucion || ''}
                  onChange={(e) => setConfiguracion({ ...configuracion, nombre_institucion: e.target.value })}
                  className="w-full border p-2 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Municipio</label>
                <input
                  value={configuracion.municipio || ''}
                  onChange={(e) => setConfiguracion({ ...configuracion, municipio: e.target.value })}
                  className="w-full border p-2 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Parroquia</label>
                <input
                  value={configuracion.parroquia || ''}
                  onChange={(e) => setConfiguracion({ ...configuracion, parroquia: e.target.value })}
                  className="w-full border p-2 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">CDCE Estadal</label>
                <input
                  value={configuracion.cdce_estadal || ''}
                  onChange={(e) => setConfiguracion({ ...configuracion, cdce_estadal: e.target.value })}
                  className="w-full border p-2 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Director Institución - Nombre</label>
                <input
                  value={configuracion.director_institucion_nombre || ''}
                  onChange={(e) => setConfiguracion({ ...configuracion, director_institucion_nombre: e.target.value })}
                  className="w-full border p-2 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Director Institución - C.I.</label>
                <input
                  value={configuracion.director_institucion_cedula || ''}
                  onChange={(e) => setConfiguracion({ ...configuracion, director_institucion_cedula: e.target.value })}
                  className="w-full border p-2 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Director CDCE - Nombre</label>
                <input
                  value={configuracion.director_cdce_nombre || ''}
                  onChange={(e) => setConfiguracion({ ...configuracion, director_cdce_nombre: e.target.value })}
                  className="w-full border p-2 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Director CDCE - C.I.</label>
                <input
                  value={configuracion.director_cdce_cedula || ''}
                  onChange={(e) => setConfiguracion({ ...configuracion, director_cdce_cedula: e.target.value })}
                  className="w-full border p-2 rounded text-sm"
                />
              </div>
            </div>
            <button
              onClick={handleGuardarConfiguracion}
              disabled={guardando}
              className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700 disabled:opacity-50 text-sm"
            >
              <Globe className="w-4 h-4" /> Guardar Datos Institucionales
            </button>
          </div>
        </details>
      </div>
    </Modal>
  );
}
