import UrlsExternasList from '../components/urlsExternas/UrlsExternasList';

/**
 * ConfiguracionUrls - Gestión de URLs externas dinámicas.
 * Ruta: /admin/dashboard/configuracion-urls
 *
 * Permite al administrador listar, editar slugs, cambiar el estado con
 * Switch (Activo/Inactivo) y gestionar fechas de expiración de formularios externos.
 */
export default function ConfiguracionUrls() {
  return <UrlsExternasList />;
}