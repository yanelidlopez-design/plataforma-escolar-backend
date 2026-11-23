import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Clock, CheckCircle, ExternalLink, Calendar, FileText } from 'lucide-react';
import UrlCerradaView from '../components/urlsExternas/UrlCerradaView';
import { getUrlExternaPublica } from '../api/urlsExternas';

/**
 * InscripcionExterna - Página pública para acceder al formulario de inscripción externa.
 *
 * Ruta: /inscripcion-externa/:token (pública, no requiere autenticación)
 *
 * Lógica:
 *  - Verifica el token en GET /api/academico/periodos/publico/<token>/
 *  - Si el periodo existe y está activo -> muestra opciones y enlace al formulario
 *  - Si no existe o está inactivo -> renderiza UrlCerradaView
 */
export default function InscripcionExterna() {
  const { token, slug } = useParams();
  const tokenValue = token || slug;

  const [periodo, setPeriodo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const verificar = async () => {
      try {
        const response = await getUrlExternaPublica(tokenValue);
        setPeriodo(response.data);
        setError(null);
      } catch (err) {
        console.error('Error al verificar URL de inscripción externa:', err);
        setPeriodo(null);
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
          <p className="text-gray-600">Verificando disponibilidad del formulario de inscripción...</p>
        </div>
      </div>
    );
  }

  // Si no se encontró el periodo o hay error o está inactivo
  if (!periodo || error || !periodo.activo_manual) {
    return <UrlCerradaView />;
  }

  // Validar fecha de expiración
  const estaExpirado = periodo.fecha_fin && new Date(periodo.fecha_fin) < new Date();
  if (estaExpirado) {
    return <UrlCerradaView />;
  }

  const formularioUrl = `/api/academico/inscripcion-externa/?token=${encodeURIComponent(tokenValue)}`;

  const formatoFecha = (fechaStr) => {
    if (!fechaStr) return null;
    try {
      const d = new Date(fechaStr);
      return d.toLocaleDateString('es-ES', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch {
      return fechaStr;
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4 py-8">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-lg border border-slate-100 p-8 text-center">
        <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-6">
          <CheckCircle className="w-8 h-8 text-emerald-600" />
        </div>

        <h1 className="text-2xl font-bold text-slate-800 mb-2">
          Proceso de Inscripción Abierto
        </h1>

        <p className="text-slate-600 mb-6">
          Bienvenido al portal de inscripción para el período{' '}
          <span className="font-semibold text-slate-900">{periodo.nombre}</span>.
        </p>

        <div className="bg-slate-50 rounded-xl p-4 mb-6 text-left space-y-2 border border-slate-100">
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <FileText className="w-4 h-4 text-primary-600 shrink-0" />
            <span>
              <strong>Período:</strong> {periodo.nombre}
            </span>
          </div>

          {periodo.fecha_inicio && (
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Calendar className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>
                <strong>Apertura:</strong> {formatoFecha(periodo.fecha_inicio)}
              </span>
            </div>
          )}

          {periodo.fecha_fin && (
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Calendar className="w-4 h-4 text-amber-600 shrink-0" />
              <span>
                <strong>Cierre:</strong> {formatoFecha(periodo.fecha_fin)}
              </span>
            </div>
          )}

          <div className="flex items-center gap-2 text-sm text-slate-600">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 ml-1 mr-1"></span>
            <span>
              <strong>Estado:</strong>{' '}
              <span className="text-emerald-700 font-semibold">Disponible</span>
            </span>
          </div>
        </div>

        <a
          href={formularioUrl}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white font-medium py-3.5 px-6 rounded-xl hover:bg-blue-700 transition shadow-sm"
        >
          <ExternalLink className="w-5 h-5" />
          Ingresar al Formulario de Inscripción
        </a>

        <p className="text-xs text-slate-400 mt-6">
          Complete todos los campos requeridos con la información del alumno y representante.
        </p>
      </div>
    </div>
  );
}
