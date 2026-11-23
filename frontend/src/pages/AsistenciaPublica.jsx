import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Clock, CheckCircle, ExternalLink, Calendar, CheckSquare } from 'lucide-react';
import UrlCerradaView from '../components/urlsExternas/UrlCerradaView';
import { getAsistenciaPublicaToken } from '../api/asistenciaPublica';

/**
 * AsistenciaPublica - Página pública para acceder al registro de asistencia pública por token.
 *
 * Ruta: /asistencia-publica/:token (pública, no requiere autenticación)
 *
 * Lógica:
 *  - Valida el token contra GET /api/core/asistencia-publica/publico/<token>/
 *  - Si el enlace existe y está activo -> muestra los datos y acceso al registro
 *  - Si no existe o está inactivo -> renderiza UrlCerradaView
 */
export default function AsistenciaPublica() {
  const { token, slug } = useParams();
  const tokenValue = token || slug;

  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const verificar = async () => {
      try {
        const response = await getAsistenciaPublicaToken(tokenValue);
        setConfig(response.data);
        setError(null);
      } catch (err) {
        console.error('Error al verificar URL de asistencia pública:', err);
        setConfig(null);
        setError(err.response?.data?.detail || 'Error al verificar el estado del formulario.');
      } finally {
        setLoading(false);
      }
    };

    if (tokenValue) {
      verificar();
    } else {
      setLoading(false);
    }
  }, [tokenValue]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Clock className="w-8 h-8 text-primary-600 mb-3 animate-spin mx-auto" />
          <p className="text-gray-600">Verificando enlace de asistencia...</p>
        </div>
      </div>
    );
  }

  // Si no se encontró, error, o no está activo
  if (!config || error || !config.activo) {
    return <UrlCerradaView />;
  }

  const formatoFecha = (fechaStr) => {
    if (!fechaStr) return null;
    try {
      const d = new Date(fechaStr.includes('T') ? fechaStr : `${fechaStr}T12:00:00`);
      return d.toLocaleDateString('es-ES', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch {
      return fechaStr;
    }
  };

  const asistenciaUrl = `/api/academico/asistencia-publica/grupos/?token=${encodeURIComponent(tokenValue)}`;

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4 py-8">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-lg border border-slate-100 p-8 text-center">
        <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-6">
          <CheckCircle className="w-8 h-8 text-emerald-600" />
        </div>

        <h1 className="text-2xl font-bold text-slate-800 mb-2">
          Control de Asistencia Pública
        </h1>

        <p className="text-slate-600 mb-6">
          Enlace habilitado para el pase y verificación de asistencia del día.
        </p>

        <div className="bg-slate-50 rounded-xl p-4 mb-6 text-left space-y-2 border border-slate-100">
          {config.fecha_dia && (
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Calendar className="w-4 h-4 text-primary-600 shrink-0" />
              <span>
                <strong>Fecha asignada:</strong> {formatoFecha(config.fecha_dia)}
              </span>
            </div>
          )}

          <div className="flex items-center gap-2 text-sm text-slate-600">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 ml-1 mr-1"></span>
            <span>
              <strong>Estado:</strong>{' '}
              <span className="text-emerald-700 font-semibold">Activo y habilitado</span>
            </span>
          </div>
        </div>

        <a
          href={asistenciaUrl}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white font-medium py-3.5 px-6 rounded-xl hover:bg-blue-700 transition shadow-sm"
        >
          <CheckSquare className="w-5 h-5" />
          Registrar Asistencia de Alumnos
        </a>

        <p className="text-xs text-slate-400 mt-6">
          Seleccione el grado y sección correspondientes para pasar lista.
        </p>
      </div>
    </div>
  );
}
