import { useParams } from 'react-router-dom';
import { ShieldAlert, Clock, Link, Home } from 'lucide-react';

/**
 * UrlCerradaView - Vista pública limpia que se renderiza cuando una URL externa
 * está desactivada (OFF) o expirada.
 * Muestra el mensaje: "Este formulario se encuentra cerrado temporalmente".
 *
 * Recibe el slug por URL para mostrar qué formulario está cerrado.
 */
export default function UrlCerradaView() {
  const { slug } = useParams();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md text-center">
        <div className="flex flex-col items-center justify-center">
          <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mb-6">
            <ShieldAlert className="w-8 h-8 text-red-600" />
          </div>

          <h1 className="text-2xl font-bold text-gray-900 mb-3">
            Este formulario se encuentra cerrado temporalmente
          </h1>

          <p className="text-gray-600 mb-6">
            El formulario de{" "}
            <span className="font-medium text-gray-900">{slug || 'este enlace'}</span>{" "}
            actualmente no está disponible. Puede estar desactivado por el administrador
            o haber alcanzado su fecha de expiración.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => window.history.back()}
              className="btn-secondary flex items-center gap-2"
            >
              <Clock className="w-4 h-4" /> Volver atrás
            </button>
            <a
              href="/admin/dashboard/configuracion-urls"
              className="btn-primary flex items-center gap-2"
            >
              <Link className="w-4 h-4" /> Ir al panel de configuración
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
