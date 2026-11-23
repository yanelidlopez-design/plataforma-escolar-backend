import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import AdminLayout from './components/layout/AdminLayout';
import Dashboard from './pages/Dashboard';
import Alumnos from './pages/Alumnos';
import Personal from './pages/Personal';
import Asistencia from './pages/Asistencia';
import Calificaciones from './pages/Calificaciones';
import ConfiguracionEnlace from './pages/ConfiguracionEnlace';
import Reportes from './pages/Reportes';
import Login from './pages/Login';
import RecuperarContrasena from './pages/RecuperarContrasena';
import InscripcionExterna from './pages/InscripcionExterna';
import AsistenciaPublica from './pages/AsistenciaPublica';
import UrlExternaPublica from './components/urlsExternas/UrlExternaPublica';

/**
 * App - Componente raíz con las rutas de la aplicación.
 * - Rutas públicas: /login, /recuperar-contrasena, /inscripcion-externa/:token, /asistencia-publica/:token
 * - Rutas protegidas: /admin/dashboard/* (requieren autenticación JWT)
 */
function App() {
  const { isAuthenticated, loading } = useAuth();

  // Mientras se verifica el token, no renderizamos nada (o un loader)
  if (loading) {
    return null;
  }

  return (
    <Routes>
      {/* Rutas públicas de autenticación */}
      <Route path="/login" element={<Login />} />
      <Route path="/recuperar-contrasena" element={<RecuperarContrasena />} />

      {/* Rutas públicas para formularios externos (accesibles sin login) */}
      <Route path="/externo/:slug" element={<UrlExternaPublica />} />
      <Route path="/inscripcion-externa/:token" element={<InscripcionExterna />} />
      <Route path="/asistencia-publica/:token" element={<AsistenciaPublica />} />

      {/* Rutas protegidas del panel admin bajo /admin/dashboard/* */}
      <Route
        path="/admin/dashboard/*"
        element={
          isAuthenticated ? <AdminLayout /> : <Navigate to="/login" replace />
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="alumnos" element={<Alumnos />} />
        <Route path="personal" element={<Personal />} />
        <Route path="asistencia" element={<Asistencia />} />
        <Route path="calificaciones" element={<Calificaciones />} />
        <Route path="configuracion-enlace" element={<ConfiguracionEnlace />} />
        <Route path="reportes" element={<Reportes />} />
      </Route>

      {/* Redirección raíz al dashboard si está autenticado, si no al login */}
      <Route
        path="/"
        element={
          isAuthenticated ? <Navigate to="/admin/dashboard" replace /> : <Navigate to="/login" replace />
        }
      />
    </Routes>
  );
}

export default App;