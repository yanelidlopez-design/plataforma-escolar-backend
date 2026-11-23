import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Clock, CheckCircle } from 'lucide-react';
import UrlCerradaView from './UrlCerradaView';
import { getAsistenciaPublicaToken } from '../../api/asistenciaPublica';

/**
 * AsistenciaPublicaPublica – Ruta pública para acceder al formulario de asistencia por token.
 *
 * Ruta: /asistencia-publica/:token  (pública, no requiere autenticación)
 *
 * Lógica:
 *  - Llama a GET /api/core/asistencia-publica/publico/<token>/ para validar el token.
 *  - Si el registro existe y está activo  → muestra el iframe del formulario de asistencia.
 *  - Si no existe o está inactivo        → renderiza UrlCerradaView.
 */
export default function AsistenciaPublicaPublica() {
  const { token } = useParams();
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const verificar = async () => {
      try {
        const response = await getAsistenciaPublicaToken(token);
        setConfig(response.data);
        setError(null);
      } catch (err) {
        console.error('Error al verificar URL de asistencia:', err);
        setConfig(null);
        setError(err.response?.data?.detail || 'Error al verificar el estado del formulario.');
      } finally {
        setLoading(false);
      }
    };
    verificar();
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Clock className="w-8 h-8 text-primary-600 mb-3 animate-spin" />
          <p className="text-gray-600">Verificando disponibilidad del formulario...</p>
        </div>
      </div>
    );
  }

  if (!config || error || !config.activo) {
    return <UrlCerradaView slug={token} />;
  }

  // Format the date for display
  const fechaFormateada = config.fecha_dia
    ? new Date(config.fecha_dia + 'T12:00:00').toLocaleDateString('es-ES', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : null;

  // Redirect to the main attendance form using the academic endpoint
  const asistenciaUrl = `/api/academico/asistencia-publica/grupos/?token=${encodeURIComponent(token)}`;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md text-center">
        <div className="flex flex-col items-center justify-center">
          <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mb-6">
            <CheckCircle className="w-8 h-8 text-green-600" />
          </div>

          <h1 className="text-2xl font-bold text-gray-900 mb-3">
            Formulario de Asistencia
          </h1>

          {fechaFormateada && (
            <p className="text-gray-600 mb-2">
              Fecha: <span className="font-medium text-gray-900">{fechaFormateada}</span>
            </p>
          )}

          <p className="text-gray-600 mb-6">
            Este formulario está disponible para registrar asistencia.
          </p>

          <a
            href={asistenciaUrl}
            className="inline-flex items-center gap-2 bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 font-medium"
            target="_blank"
            rel="noopener noreferrer"
          >
            Registrar Asistencia
          </a>

          <div className="mt-6 pt-6 border-t border-gray-200 w-full">
            <p className="text-xs text-gray-500">
              <strong>Estado:</strong>{' '}
              <span className="text-green-600 font-medium">Activo</span>
              {fechaFormateada && (
                <>
                  <br />
                  <strong>Fecha:</strong> {fechaFormateada}
                </>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
