import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/common/Card';
import Modal from '../components/common/Modal';
import { toast } from 'react-toastify';
import { Globe, Clock, Layout, Mail, Plus, Copy, ExternalLink } from 'lucide-react';

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
} from '../api/asistenciaPublica';

/** Página unificada para gestionar enlaces de inscripción y asistencia */
export default function ConfiguracionEnlace() {
  const [activeTab, setActiveTab] = useState('inscripcion');

  const [inscripcionUrls, setInscripcionUrls] = useState([]);
  const [loadingInscripcion, setLoadingInscripcion] = useState(true);

  const [asistenciaEnlaces, setAsistenciaEnlaces] = useState([]);
  const [loadingAsistencia, setLoadingAsistencia] = useState(true);
  const [enlaceActivoHoy, setEnlaceActivoHoy] = useState(null);

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
        if (resp.data && resp.data.token_acceso) {
          setEnlaceActivoHoy(resp.data);
          // Asegurar que aparezca en la lista si no está ya
          const yaExiste = asistenciaEnlaces.some(
            (e) => e.id === resp.data.id || e.token_acceso === resp.data.token_acceso,
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
  }, [activeTab, asistenciaEnlaces]);

  const cargarDatos = async () => {
    try {
      setLoadingInscripcion(true);
      setLoadingAsistencia(true);
      const res = await getUrlsExternas();
      setInscripcionUrls(Array.isArray(res.data) ? res.data : (res.data.results || res.data || []));
      const resAsist = await listarEnlaceAsistencia();
      setAsistenciaEnlaces(Array.isArray(resAsist.data) ? resAsist.data : (resAsist.data.results || resAsist.data || []));
    } catch (e) {
      toast.error('Error al cargar enlaces');
    } finally {
      setLoadingInscripcion(false);
      setLoadingAsistencia(false);
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
                      <button onClick={() => { if (confirm('¿Eliminar?')) { deleteUrlExterna(url.id).then(() => cargarDatos()); } }} className="text-red-600 hover:underline text-sm">Eliminar</button>
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
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-800">Enlaces de Asistencia Pública</h2>
            <button
              onClick={() => {
                setType('asistencia');
                setEditingId(null);
                const now = new Date();
                const fechaInicio = now.toISOString().slice(0, 16); // YYYY-MM-DDTHH:mm
                setInscripcionData({
                  nombre: `Asistencia ${now.getFullYear()}`,
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
              {enlaceActivoHoy && (
                <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex items-start gap-2">
                    <ExternalLink className="w-4 h-4 text-blue-600 mt-0.5" />
                    <div>
                      <div className="text-sm font-semibold text-blue-800">
                        Enlace activo de asistencia para hoy
                      </div>
                      <div className="text-xs text-blue-700 mt-1">
                        Fecha: {enlaceActivoHoy.fecha_dia || 'N/A'}
                      </div>
                    </div>
                  </div>
                  <div className="mt-2 space-y-2">
                    <div className="flex items-center gap-2 bg-white p-2 rounded border border-blue-100">
                      <input
                        type="text"
                        readOnly
                        value={`${window.location.origin}/asistencia-publica/${enlaceActivoHoy.token_acceso}`}
                        className="flex-1 text-xs font-mono text-gray-700 bg-transparent border-0 focus:ring-0 sm:text-sm"
                      />
                      <button
                        onClick={() => {
                          const url = `${window.location.origin}/asistencia-publica/${enlaceActivoHoy.token_acceso}`;
                          navigator.clipboard.writeText(url);
                          toast.success('Enlace copiado al portapapeles');
                        }}
                        className="flex items-center gap-1 bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 text-xs"
                        title="Copiar Enlace"
                      >
                        <Copy className="w-3 h-3" />
                      </button>
                    </div>
                    <a
                      href={`${window.location.origin}/asistencia-publica/${enlaceActivoHoy.token_acceso}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-blue-600 hover:text-blue-800 text-xs underline hover:no-underline"
                    >
                      <ExternalLink className="w-3 h-3" /> Abrir enlace de hoy
                    </a>
                  </div>
                </div>
              )}
              <div className="space-y-2">
                {asistenciaEnlaces.map((enlace) => {
                  const urlCompleta = `${window.location.origin}/asistencia-publica/${enlace.token_acceso}`;
                  return (
                    <div key={enlace.id} className="border p-3 rounded bg-white">
                      <div className="text-sm text-gray-600">
                        Fecha: {enlace.fecha_dia || 'N/A'}
                      </div>
                      <div className="text-sm text-gray-600">
                        Estado: {enlace.activo ? 'Activo' : 'Inactivo'}
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
                          setEditingId(enlace.id); setType('asistencia');
                          setInscripcionData({
                            nombre: enlace.nombre || `Asistencia ${enlace.fecha_dia || ''}`,
                            fecha_inicio: enlace.fecha_dia ? new Date(enlace.fecha_dia).toISOString().slice(0, 16) : '',
                            activo: enlace.activo, token_acceso: enlace.token_acceso || '',
                            fecha_vigencia_inicio: enlace.fecha_vigencia_inicio || '',
                            fecha_vigencia_fin: enlace.fecha_vigencia_fin || '',
                          });
                          setModalOpen(true);
                        }} className="text-blue-600 hover:underline text-sm">Editar</button>
                        <button onClick={() => { if (confirm('¿Eliminar?')) { eliminarEnlaceAsistencia(enlace.id).then(() => cargarDatos()); } }} className="text-red-600 hover:underline text-sm">Eliminar</button>
                      </div>
                    </div>
                  );
                })}
                {asistenciaEnlaces.length === 0 && (
                  <p className="text-gray-500 text-sm text-center py-4">Sin enlaces de asistencia pública</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Modal */}
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? 'Editar Enlace' : 'Nuevo Enlace'}>
        <div className="space-y-3">
          <div><label className="block text-sm font-medium text-gray-700">Nombre del Período:</label><input type="text" value={inscripcionData.nombre} onChange={e => setInscripcionData({...inscripcionData, nombre: e.target.value})} placeholder="Ej: Inscripciones 2026-2027" className="w-full border p-2 rounded" /></div>
          <div><label className="block text-sm font-medium text-gray-700">Fecha de Inicio:</label><input type="datetime-local" value={inscripcionData.fecha_inicio} onChange={e => setInscripcionData({...inscripcionData, fecha_inicio: e.target.value})} className="w-full border p-2 rounded" /></div>
          <div><label className="block text-sm font-medium text-gray-700">Vigencia Fin:</label><input type="datetime-local" value={inscripcionData.fecha_vigencia_fin} onChange={e => setInscripcionData({...inscripcionData, fecha_vigencia_fin: e.target.value})} className="w-full border p-2 rounded" /></div>
          <div><label className="block text-sm font-medium text-gray-700">Activo:</label><select value={String(inscripcionData.activo)} onChange={e => setInscripcionData({...inscripcionData, activo: e.target.value === 'true'})} className="w-full border p-2 rounded"><option value="true">Activo</option><option value="false">Inactivo</option></select></div>
          <div><label className="block text-sm font-medium text-gray-700">Token / Código:</label><input type="text" value={inscripcionData.token_acceso} onChange={e => setInscripcionData({...inscripcionData, token_acceso: e.target.value})} placeholder="Generar automáticamente" className="w-full border p-2 rounded" /></div>
          <div className="flex gap-2 pt-2">
            <button onClick={() => {
              // Mapear nombres de campos del frontend al backend de PeriodoInscripcion
              const data = {
                nombre: inscripcionData.nombre,
                fecha_inicio: inscripcionData.fecha_inicio,
                fecha_fin: inscripcionData.fecha_vigencia_fin,
                activo_manual: inscripcionData.activo,
                token_acceso: inscripcionData.token_acceso || undefined,
              };
              if (editingId) {
                if (type === 'asistencia') {
                  actualizarEnlaceAsistencia(editingId, data).then(() => { toast.success('Actualizado'); setModalOpen(false); setEditingId(null); cargarDatos(); });
                } else {
                  updateUrlExterna(editingId, data).then(() => { toast.success('Actualizado'); setModalOpen(false); setEditingId(null); cargarDatos(); });
                }
              } else {
                if (type === 'asistencia') {
                  crearEnlaceAsistencia(data).then(() => { toast.success('Creado'); setModalOpen(false); setEditingId(null); cargarDatos(); });
                } else {
                  createUrlExterna(data).then(() => { toast.success('Creado'); setModalOpen(false); setEditingId(null); cargarDatos(); });
                }
              }
            }} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Guardar</button>
            <button onClick={() => setModalOpen(false)} className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-100">Cancelar</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
