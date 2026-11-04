import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ShieldAlert, Clock, Link, Home, CheckCircle, AlertCircle } from 'lucide-react';
import UrlCerradaView from './UrlCerradaView';
import { getUrlExternaPublica } from '../../api/urlsExternas';

/**
 * UrlExternaPublica - Ruta pública para acceder a formularios externos por slug.
 *
 * Lógica del enrutador:
 *  - Carga todas las URLs externas configuradas
 *  - Busca el slug coincidente en la URL (/externo/:slug)
 *  - Si la URL existe y está ACTIVA -> redirige al formulario externo correspondiente
 *  - Si la URL está INACTIVA (OFF) o expirada -> renderiza UrlCerradaView con el mensaje:
 *    "Este formulario se encuentra cerrado temporalmente"
 *
 * Ruta: /externo/:slug  (pública, no requiere autenticación)
 */
export default function UrlExternaPublica() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [urlExterna, setUrlExterna] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const verificarUrl = async () => {
      try {
        const response = await getUrlExternaPublica(slug);
        setUrlExterna(response.data);
        setError(null);
      } catch (err) {
        console.error('Error al verificar URL externa:', err);
        setUrlExterna(null);
        setError(err.response?.data?.detail || 'Error al verificar el estado del formulario.');
      } finally {
        setLoading(false);
      }
    };
    verificarUrl();
  }, [slug]);

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

  // URL no encontrada en el sistema
  if (!urlExterna || error) {
    return <UrlCerradaView slug={slug} />;
  }

  // URL encontrada pero inactiva o expirada
  const estaExpirada = urlExterna.fecha_fin && new Date(urlExterna.fecha_fin) < new Date();
  if (!urlExterna.activo_manual || estaExpirada) {
    return <UrlCerradaView slug={slug} />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md text-center">
        <div className="flex flex-col items-center justify-center">
          <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mb-6">
            <CheckCircle className="w-8 h-8 text-green-600" />
          </div>

          <h1 className="text-2xl font-bold text-gray-900 mb-3">
            Formulario disponible
          </h1>

          <p className="text-gray-600 mb-6">
            El formulario <span className="font-medium text-gray-900">{urlExterna.nombre}</span>
            está actualmente Activo y disponible públicamente.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => {
                const formularioUrl = `/api/academico/inscripcion-externa/?token=${encodeURIComponent(slug)}`;
                window.open(formularioUrl, '_blank', 'noopener,noreferrer');
              }}
              className="btn-primary flex items-center gap-2"
            >
              <Link className="w-4 h-4" /> Abrir formulario
            </button>
            <a
              href="/admin/dashboard/configuracion-urls"
              className="btn-secondary flex items-center gap-2"
            >
              <Home className="w-4 h-4" /> Panel de configuración
            </a>
          </div>

          <div className="mt-6 pt-6 border-t border-gray-200">
            <p className="text-xs text-gray-500">
              <strong>Enlace:</strong> /externo/{slug}<br />
              <strong>Estado:</strong> <span className="text-green-600 font-medium">Activo</span><br />
              <strong>Expiración:</strong>{' '}
              {urlExterna.fecha_fin ? new Date(urlExterna.fecha_fin).toLocaleDateString('es-ES') : 'Sin expiración'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
