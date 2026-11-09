import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/common/Card';
import Modal from '../components/common/Modal';
import { toast } from 'react-toastify';

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
} from '../api/asistenciaPublica';

/** Página unificada para gestionar enlaces de inscripción y asistencia */
export default function ConfiguracionEnlace() {
  const [inscripcionUrls, setInscripcionUrls] = useState([]);
  const [loadingInscripcion, setLoadingInscripcion] = useState(true);

  const [asistenciaEnlaces, setAsistenciaEnlaces] = useState([]);
  const [loadingAsistencia, setLoadingAsistencia] = useState(true);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [type, setType] = useState('inscripcion');
  const [inscripcionData, setInscripcionData] = useState({
    fecha_dia: '', activo: true, token_acceso: '',
    fecha_vigencia_inicio: '', fecha_vigencia_fin: '',
  });

  useEffect(() => { cargarDatos(); }, []);

  const cargarDatos = async () => {
    try {
      setLoadingInscripcion(true);
      const res = await getUrlsExternas();
      setInscripcionUrls(res.data.results || res.data || []);
      const resAsist = await listarEnlaceAsistencia();
      setAsistenciaEnlaces(resAsist.data.results || resAsist.data || []);
    } catch (e) {
      toast.error('Error al cargar enlaces');
    } finally {
      setLoadingInscripcion(false);
      setLoadingAsistencia(false);
    }
  };

  if (loadingInscripcion && loadingAsistencia) {
    return <p className="text-center">Cargando enlaces...</p>;
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Gestión de Enlaces de Acceso</h1>
      <p className="text-gray-600 mb-6">Administra los enlaces públicos de inscripción y asistencia</p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ENLACES DE INSCRIPCIÓN */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="w-5 h-5" /> Enlaces de Inscripción
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {inscripcionUrls.map((url) => (
                <div key={url.id} className="border p-3 rounded mb-2 bg-white">
                  <div className="font-mono text-sm mb-1">{url.token_acceso?.substring(0, 20)}...</div>
                  <div className="text-sm text-gray-600">Servicio: {url.nombre}</div>
                  <div className="text-sm text-gray-600">Estado: {url.activo_manual ? '<span className="text-green-600 font-medium">Activo</span>' : '<span className="text-red-600 font-medium">Inactivo</span>'}</div>
                  <div className="flex gap-2 mt-2">
                    <button onClick={() => {
                      setEditingId(url.id); setType('inscripcion');
                      setInscripcionData({
                        fecha_dia: url.fecha_inicio?.split('T')[0] || '',
                        activo: url.activo_manual, token_acceso: url.token_acceso || '',
                        fecha_vigencia_inicio: url.fecha_vigencia_inicio || '',
                        fecha_vigencia_fin: url.fecha_vigencia_fin || '',
                      });
                      setModalOpen(true);
                    }} className="text-blue-600 hover:underline text-sm">Editar</button>
                    <button onClick={() => { if (confirm('¿Eliminar?')) { deleteUrlExterna(url.id).then(() => cargarDatos()); } }} className="text-red-600 hover:underline text-sm">Eliminar</button>
                  </div>
                </div>
              ))}
              {inscripcionUrls.length === 0 && <p className="text-gray-500 text-sm">Sin enlaces de inscripción</p>}
            </div>
          </CardContent>
        </Card>

        {/* ENLACES DE ASISTENCIA */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="w-5 h-5" /> Enlaces de Asistencia
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {asistenciaEnlaces.map((enlace) => (
                <div key={enlace.id} className="border p-3 rounded mb-2 bg-white">
                  <div className="font-mono text-sm mb-1">{enlace.token_acceso?.substring(0, 20)}...</div>
                  <div className="text-sm text-gray-600">Fecha: {enlace.fecha_dia}</div>
                  <div className="text-sm text-gray-600">Estado: {enlace.activo ? '<span className="text-green-600 font-medium">Activo</span>' : '<span className="text-red-600 font-medium">Inactivo</span>'}</div>
                  <div className="flex gap-2 mt-2">
                    <button onClick={() => {
                      setEditingId(enlace.id); setType('asistencia');
                      setInscripcionData({
                        fecha_dia: enlace.fecha_dia, activo: enlace.activo,
                        token_acceso: enlace.token_acceso || '',
                        fecha_vigencia_inicio: enlace.fecha_vigencia_inicio || '',
                        fecha_vigencia_fin: enlace.fecha_vigencia_fin || '',
                      });
                      setModalOpen(true);
                    }} className="text-blue-600 hover:underline text-sm">Editar</button>
                    <button onClick={() => { if (confirm('¿Eliminar?')) { eliminarEnlaceAsistencia(enlace.id).then(() => cargarDatos()); } }} className="text-red-600 hover:underline text-sm">Eliminar</button>
                  </div>
                </div>
              ))}
              {asistenciaEnlaces.length === 0 && <p className="text-gray-500 text-sm">Sin enlaces de asistencia</p>}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Modal */}
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editingId ? 'Editar Enlace' : 'Nuevo Enlace'}>
        <div className="space-y-3">
          <div><label>Fecha:</label><input type="date" value={inscripcionData.fecha_dia} onChange={e => setInscripcionData({...inscripcionData, fecha_dia: e.target.value})} className="w-full border p-2 rounded" /></div>
          <div><label>Activo:</label><select value={inscripcionData.activo} onChange={e => setInscripcionData({...inscripcionData, activo: e.target.value === 'true'})} className="w-full border p-2 rounded"><option value={true}>Activo</option><option value={false}>Inactivo</option></select></div>
          <div><label>Token/Código:</label><input type="text" value={inscripcionData.token_acceso} onChange={e => setInscripcionData({...inscripcionData, token_acceso: e.target.value})} placeholder="Generar automáticamente" className="w-full border p-2 rounded" /></div>
          <div><label>Vigencia Inicio:</label><input type="datetime-local" value={inscripcionData.fecha_vigencia_inicio} onChange={e => setInscripcionData({...inscripcionData, fecha_vigencia_inicio: e.target.value})} className="w-full border p-2 rounded" /></div>
          <div><label>Vigencia Fin:</label><input type="datetime-local" value={inscripcionData.fecha_vigencia_fin} onChange={e => setInscripcionData({...inscripcionData, fecha_vigencia_fin: e.target.value})} className="w-full border p-2 rounded" /></div>
          <div className="flex gap-2 pt-2">
            <button onClick={() => {
              const data = { ...inscripcionData, activo: inscripcionData.activo };
              if (editingId) {
                if (type === 'asistencia') {
                  actualizarEnlaceAsistencia(editingId, data).then(() => { toast.success('Actualizado'); setModalOpen(false); setEditingId(null); cargarDatos(); });
                } else { toast.info('Actualizando inscripción...'); }
              } else {
                if (type === 'asistencia') {
                  crearEnlaceAsistencia(data).then(() => { toast.success('Creado'); setModalOpen(false); setEditingId(null); cargarDatos(); });
                } else { toast.info('Creando inscripción...'); }
              }
            }} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Guardar</button>
            <button onClick={() => setModalOpen(false)} className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-100">Cancelar</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
