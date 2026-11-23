import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/common/Card';
import Modal from '../components/common/Modal';
import { toast } from 'react-toastify';
import { Globe, Clock, Layout, Mail, Plus, Copy, ExternalLink, RotateCw, Calendar, CheckCircle } from 'lucide-react';

// APIs para URLs de inscripción (módulo academico)
import {
  getUrlsExternas,
  createUrlExterna,
  updateUrlExterna,
  deleteUrlExterna,
} from '../api/urlsExternas';

// API para enlaces de asistencia (módulo core)
import {
  listarEnlaceAsistencia,
  crearEnlaceAsistencia,
  actualizarEnlaceAsistencia,
  eliminarEnlaceAsistencia,
  obtenerEnlaceActivo,
  regenerarEnlaceAsistencia,
} from '../api/asistenciaPublica';

/** Página unificada para gestionar enlaces de inscripción y asistencia */
export default function ConfiguracionEnlace() {
  const [activeTab, setActiveTab] = useState('inscripcion');

  const [inscripcionUrls, setInscripcionUrls] = useState([]);
  const [loadingInscripcion, setLoadingInscripcion] = useState(true);

  const [asistenciaEnlaces, setAsistenciaEnlaces] = useState([]);
  const [loadingAsistencia, setLoadingAsistencia] = useState(true);
  const [enlaceActivoHoy, setEnlaceActivoHoy] = useState(null);
  const [regenerando, setRegenerando] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [type, setType] = useState('inscripcion');
  const [inscripcionData, setInscripcionData] = useState({
    nombre: '', fecha_inicio: '', activo: true, token_acceso: '',
    fecha_vigencia_inicio: '', fecha_vigencia_fin: '',
  });

  useEffect(() => { cargarDatos(); }, []);

  // Cargar el enlace activo de asistencia para hoy cuando la pestaña de asistencia esté activa
  useEffect(() => {
    if (activeTab !== 'asistencia') return;
    const cargarEnlaceActivo = async () => {
      try {
        const resp = await obtenerEnlaceActivo();
        if (resp.data && (resp.data.token_acceso || resp.data.token)) {
          setEnlaceActivoHoy(resp.data);
          const respId = resp.data.id || resp.data.id_config;
          const yaExiste = asistenciaEnlaces.some(
            (e) => (e.id || e.id_config) === respId || e.token_acceso === resp.data.token_acceso,
          );
          if (!yaExiste) {
            setAsistenciaEnlaces((prev) => [resp.data, ...prev]);
          }
        }
      } catch (e) {
        // No hay enlace activo hoy; no es error crítico
      }
    };
    cargarEnlaceActivo();
  }, [activeTab]);

  const cargarDatos = async () => {
    try {
      setLoadingInscripcion(true);
      setLoadingAsistencia(true);
      const res = await getUrlsExternas();
      setInscripcionUrls(Array.isArray(res.data) ? res.data : (res.data.results || res.data || []));
      const resAsist = await listarEnlaceAsistencia();
      const asistData = Array.isArray(resAsist.data) ? resAsist.data : (resAsist.data.results || resAsist.data || []);
      setAsistenciaEnlaces(asistData);

      const hoyStr = new Date().toISOString().slice(0, 10);
      const enlaceHoy = asistData.find(e => e.activo && (e.fecha_dia === hoyStr || !e.fecha_dia)) || asistData.find(e => e.activo) || null;
      if (enlaceHoy) {
        setEnlaceActivoHoy(enlaceHoy);
      }
    } catch (e) {
      toast.error('Error al cargar enlaces');
    } finally {
      setLoadingInscripcion(false);
      setLoadingAsistencia(false);
    }
  };

  const handleRegenerarTokenHoy = async () => {
    if (!window.confirm('¿Desea regenerar el token de asistencia para hoy? El enlace anterior dejará de funcionar.')) {
      return;
    }
    try {
      setRegenerando(true);
      const resp = await regenerarEnlaceAsistencia();
      const nuevoEnlace = resp.data;
      setEnlaceActivoHoy(nuevoEnlace);
      setAsistenciaEnlaces((prev) => {
        const idNuevo = nuevoEnlace.id || nuevoEnlace.id_config;
        const filtrados = prev.filter(
          (e) => (e.id || e.id_config) !== idNuevo && e.fecha_dia !== nuevoEnlace.fecha_dia
        );
        return [nuevoEnlace, ...filtrados];
      });
      toast.success('Token de asistencia para hoy regenerado correctamente');
    } catch (err) {
      console.error('Error al regenerar token de asistencia:', err);
      toast.error(err.response?.data?.detail || 'Error al regenerar el token de asistencia');
    } finally {
      setRegenerando(false);
    }
  };

  const formatearFecha = (fechaStr) => {
    if (!fechaStr) return 'N/A';
    try {
      const d = new Date(fechaStr.includes('T') ? fechaStr : `${fechaStr}T12:00:00`);
      if (isNaN(d.getTime())) return fechaStr;
      return d.toLocaleDateString('es-ES', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return fechaStr;
    }
  };

  const handleEliminarInscripcion = async (id) => {
    if (!window.confirm('¿Está seguro de que desea eliminar este enlace de inscripción?')) {
      return;
    }
    try {
      await deleteUrlExterna(id);
      setInscripcionUrls((prev) => prev.filter((u) => u.id !== id));
      toast.success('Enlace de inscripción eliminado correctamente');
    } catch (err) {
      console.error('Error al eliminar enlace de inscripción:', err);
      toast.error('Error al eliminar el enlace de inscripción');
    }
  };

  const handleEliminarAsistencia = async (enlace) => {
    const id = enlace.id || enlace.id_config;
    if (!id) {
      toast.error('No se pudo identificar el enlace a eliminar.');
      return;
    }
    if (!window.confirm('¿Está seguro de que desea eliminar este enlace de asistencia?')) {
      return;
    }
    try {
      await eliminarEnlaceAsistencia(id);
      setAsistenciaEnlaces((prev) => prev.filter((e) => (e.id || e.id_config) !== id));
      if (enlaceActivoHoy && (enlaceActivoHoy.id === id || enlaceActivoHoy.id_config === id)) {
        setEnlaceActivoHoy(null);
      }
      toast.success('Enlace de asistencia pública eliminado correctamente');
    } catch (err) {
      console.error('Error al eliminar enlace de asistencia:', err);
      toast.error(err.response?.data?.detail || 'Error al eliminar el enlace de asistencia');
    }
  };

  if (loadingInscripcion && loadingAsistencia) {
    return <div className="p-6 text-center text-gray-500">Cargando enlaces...</div>;
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Gestión de Enlaces de Acceso</h1>
      <p className="text-gray-600 mb-6">Administra los enlaces públicos de inscripción y asistencia</p>

      {/* Pestañas */}
      <div className="flex gap-4 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('inscripcion')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 ${
            activeTab === 'inscripcion'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Layout className="w-4 h-4" /> Inscripción Externa
        </button>
        <button
          onClick={() => setActiveTab('asistencia')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 ${
            activeTab === 'asistencia'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Mail className="w-4 h-4" /> Asistencia Pública
        </button>
      </div>

      {activeTab === 'inscripcion' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-800">Enlaces de Inscripción Externa</h2>
            <button
              onClick={() => {
                setType('inscripcion');
                setEditingId(null);
                const now = new Date();
                const fechaInicio = now.toISOString().slice(0, 16); // YYYY-MM-DDTHH:mm
                setInscripcionData({
                  nombre: `Inscripciones ${now.getFullYear()}-${now.getFullYear() + 1}`,
                  fecha_inicio: fechaInicio,
                  activo: true, token_acceso: '',
                  fecha_vigencia_inicio: '', fecha_vigencia_fin: '',
                });
                setModalOpen(true);
              }}
              className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm"
            >
              <Plus className="w-4 h-4" /> Nuevo Enlace
            </button>
          </div>

          <Card>
            <CardContent className="p-4">
              <div className="space-y-2">
                {inscripcionUrls.map((url) => {
                const urlCompleta = `${window.location.origin}/inscripcion-externa/${url.token_acceso}`;
                return (
                  <div key={url.id} className="border p-3 rounded bg-white">
                    <div className="text-sm text-gray-600">Servicio: {url.nombre || 'N/A'}</div>
                    <div className="text-sm text-gray-600">
                      Estado: {url.activo_manual ? 'Activo' : 'Inactivo'}
                    </div>
                    <div className="mt-2 space-y-2">
                      <div className="flex items-center gap-2 bg-gray-50 p-2 rounded border border-gray-100">
                        <input
                          type="text"
                          readOnly
                          value={urlCompleta}
                          className="flex-1 text-xs font-mono text-gray-700 bg-transparent border-0 focus:ring-0 sm:text-sm"
                        />
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(urlCompleta);
                            toast.success('Enlace copiado al portapapeles');
                          }}
                          className="flex items-center gap-1 bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 text-xs"
                          title="Copiar Enlace"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      </div>
                      <a
                        href={urlCompleta}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-blue-600 hover:text-blue-800 text-xs underline hover:no-underline"
                      >
                        <ExternalLink className="w-3 h-3" /> Abrir
                      </a>
                    </div>
                    <div className="flex gap-2 mt-2">
                      <button onClick={() => {
                        setEditingId(url.id); setType('inscripcion');
                        setInscripcionData({
                          nombre: url.nombre || '',
                          fecha_inicio: url.fecha_inicio?.split('T')[0]?.slice(0, 16) || '',
                          activo: url.activo_manual, token_acceso: url.token_acceso || '',
                          fecha_vigencia_inicio: url.fecha_vigencia_inicio || '',
                          fecha_vigencia_fin: url.fecha_vigencia_fin || '',
                        });
                        setModalOpen(true);
                      }} className="text-blue-600 hover:underline text-sm">Editar</button>
                      <button onClick={() => handleEliminarInscripcion(url.id)} className="text-red-600 hover:underline text-sm">Eliminar</button>
                    </div>
                  </div>
                );
              })}
                {inscripcionUrls.length === 0 && (
                  <p className="text-gray-500 text-sm text-center py-4">Sin enlaces de inscripción externa</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'asistencia' && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-gray-800">Enlaces de Asistencia Pública</h2>
            <p className="text-sm text-gray-500 mt-1">
              El enlace de asistencia se genera y renueva automáticamente cada jornada. Puede compartirlo directamente o regenerar el token si requiere revocar el actual.
            </p>
          </div>

          {/* Tarjeta destacada del enlace de hoy */}
          <Card className="border-2 border-blue-200 bg-gradient-to-br from-blue-50/70 via-white to-blue-50/40 shadow-sm">
            <CardContent className="p-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold shadow-sm">
                    <Calendar className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-gray-900">
                      Enlace de Asistencia de Hoy
                    </h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-blue-700 font-medium">
                        Fecha: {formatearFecha(enlaceActivoHoy?.fecha_dia || enlaceActivoHoy?.fecha_creacion || new Date().toISOString().slice(0, 10))}
                      </span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                        Activo
                      </span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleRegenerarTokenHoy}
                  disabled={regenerando}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition shadow-sm"
                  title="Invalida el token actual y genera uno nuevo para la jornada de hoy"
                >
                  <RotateCw className={`w-3.5 h-3.5 ${regenerando ? 'animate-spin' : ''}`} />
                  {regenerando ? 'Regenerando...' : 'Regenerar Token'}
                </button>
              </div>

              {enlaceActivoHoy ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 bg-white p-2.5 rounded-xl border border-blue-100 shadow-inner">
                    <input
                      type="text"
                      readOnly
                      value={`${window.location.origin}/asistencia-publica/${enlaceActivoHoy.token_acceso || enlaceActivoHoy.token}`}
                      className="flex-1 text-xs font-mono text-gray-800 bg-transparent border-0 focus:ring-0 sm:text-sm select-all"
                    />
                    <button
                      onClick={() => {
                        const url = `${window.location.origin}/asistencia-publica/${enlaceActivoHoy.token_acceso || enlaceActivoHoy.token}`;
                        navigator.clipboard.writeText(url);
                        toast.success('Enlace de asistencia copiado al portapapeles');
                      }}
                      className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 text-xs font-medium transition shadow-sm"
                      title="Copiar Enlace"
                    >
                      <Copy className="w-3.5 h-3.5" /> Copiar Enlace
                    </button>
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs text-gray-500 pt-1 gap-2">
                    <span className="flex items-center gap-1.5 text-emerald-700 font-medium">
                      <CheckCircle className="w-4 h-4 text-emerald-600" />
                      Listo para compartir con los docentes del plantel
                    </span>
                    <a
                      href={`${window.location.origin}/asistencia-publica/${enlaceActivoHoy.token_acceso || enlaceActivoHoy.token}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 font-medium hover:underline"
                    >
                      <ExternalLink className="w-3.5 h-3.5" /> Abrir enlace de hoy
                    </a>
                  </div>
                </div>
              ) : (
                <div className="text-center py-4 text-sm text-gray-500">
                  Cargando enlace activo de hoy...
                </div>
              )}
            </CardContent>
          </Card>

          {/* Historial de enlaces */}
          <div>
            <h3 className="text-md font-semibold text-gray-700 mb-3">Historial de Enlaces de Asistencia</h3>
            <Card>
              <CardContent className="p-4">
                <div className="space-y-2">
                  {asistenciaEnlaces.map((enlace) => {
                    const enlaceId = enlace.id || enlace.id_config;
                    const token = enlace.token_acceso || enlace.token;
                    const urlCompleta = `${window.location.origin}/asistencia-publica/${token}`;
                    return (
                      <div key={enlaceId || token} className="border p-3 rounded-lg bg-white shadow-xs">
                        <div className="flex justify-between items-start">
                          <div>
                            <div className="text-sm font-medium text-gray-800">
                              Fecha: {formatearFecha(enlace.fecha_dia || enlace.fecha_creacion || enlace.created_at)}
                            </div>
                            <div className="text-xs text-gray-500 mt-0.5">
                              Estado:{' '}
                              <span className={`font-semibold ${enlace.activo ? 'text-emerald-600' : 'text-gray-500'}`}>
                                {enlace.activo ? 'Activo' : 'Inactivo'}
                              </span>
                            </div>
                          </div>
                          <button
                            onClick={() => handleEliminarAsistencia(enlace)}
                            className="text-red-600 hover:text-red-800 text-xs font-medium hover:underline"
                          >
                            Eliminar
                          </button>
                        </div>
                        <div className="mt-2 flex items-center gap-2 bg-gray-50 p-2 rounded border border-gray-100">
                          <input
                            type="text"
                            readOnly
                            value={urlCompleta}
                            className="flex-1 text-xs font-mono text-gray-700 bg-transparent border-0 focus:ring-0 select-all"
                          />
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(urlCompleta);
                              toast.success('Enlace copiado al portapapeles');
                            }}
                            className="flex items-center gap-1 bg-gray-200 text-gray-700 hover:bg-gray-300 px-2 py-1 rounded text-xs"
                            title="Copiar Enlace"
                          >
                            <Copy className="w-3 h-3" />
                          </button>
                          <a
                            href={urlCompleta}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 p-1"
                            title="Abrir enlace"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        </div>
                      </div>
                    );
                  })}
                  {asistenciaEnlaces.length === 0 && (
                    <p className="text-gray-500 text-sm text-center py-4">Sin enlaces de asistencia registrados</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Modal solo para inscripción */}
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? 'Editar Enlace de Inscripción' : 'Nuevo Enlace de Inscripción'}>
        <div className="space-y-3">
          <div><label className="block text-sm font-medium text-gray-700">Nombre del Período:</label><input type="text" value={inscripcionData.nombre} onChange={e => setInscripcionData({...inscripcionData, nombre: e.target.value})} placeholder="Ej: Inscripciones 2026-2027" className="w-full border p-2 rounded" /></div>
          <div><label className="block text-sm font-medium text-gray-700">Fecha de Inicio:</label><input type="datetime-local" value={inscripcionData.fecha_inicio} onChange={e => setInscripcionData({...inscripcionData, fecha_inicio: e.target.value})} className="w-full border p-2 rounded" /></div>
          <div><label className="block text-sm font-medium text-gray-700">Vigencia Fin:</label><input type="datetime-local" value={inscripcionData.fecha_vigencia_fin} onChange={e => setInscripcionData({...inscripcionData, fecha_vigencia_fin: e.target.value})} className="w-full border p-2 rounded" /></div>
          <div><label className="block text-sm font-medium text-gray-700">Activo:</label><select value={String(inscripcionData.activo)} onChange={e => setInscripcionData({...inscripcionData, activo: e.target.value === 'true'})} className="w-full border p-2 rounded"><option value="true">Activo</option><option value="false">Inactivo</option></select></div>
          <div><label className="block text-sm font-medium text-gray-700">Token / Código:</label><input type="text" value={inscripcionData.token_acceso} onChange={e => setInscripcionData({...inscripcionData, token_acceso: e.target.value})} placeholder="Generar automáticamente" className="w-full border p-2 rounded" /></div>
          <div className="flex gap-2 pt-2">
            <button onClick={() => {
              const data = {
                nombre: inscripcionData.nombre,
                fecha_inicio: inscripcionData.fecha_inicio,
                fecha_fin: inscripcionData.fecha_vigencia_fin,
                activo_manual: inscripcionData.activo,
                token_acceso: inscripcionData.token_acceso || undefined,
              };
              if (editingId) {
                updateUrlExterna(editingId, data).then(() => { toast.success('Actualizado'); setModalOpen(false); setEditingId(null); cargarDatos(); });
              } else {
                createUrlExterna(data).then(() => { toast.success('Creado'); setModalOpen(false); setEditingId(null); cargarDatos(); });
              }
            }} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Guardar</button>
            <button onClick={() => setModalOpen(false)} className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-100">Cancelar</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
