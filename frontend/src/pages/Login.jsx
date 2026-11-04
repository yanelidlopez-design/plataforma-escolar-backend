import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ShieldAlert, Mail, Lock } from 'lucide-react';

/**
 * Login - Página de autenticación con JWT.
 * Ruta: /login
 */
export default function Login() {
  const [credentials, setCredentials] = useState({ nombre_usuario: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await login(credentials);
      navigate('/admin/dashboard');
    } catch (err) {
      setError('Usuario o contraseña incorrectos.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <ShieldAlert className="w-12 h-12 text-primary-600 mb-4" />
          <h1 className="text-2xl font-bold text-gray-900">Plataforma Escolar</h1>
          <p className="text-sm text-gray-500">Iniciar sesión en el panel administrativo</p>
        </div>

        <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Usuario
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  name="nombre_usuario"
                  placeholder="Ingresa tu usuario"
                  className="input-field pl-10"
                  value={credentials.nombre_usuario}
                  onChange={(e) =>
                    setCredentials({ ...credentials, nombre_usuario: e.target.value })
                  }
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Contraseña
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="password"
                  name="password"
                  placeholder="••••••••"
                  className="input-field pl-10"
                  value={credentials.password}
                  onChange={(e) =>
                    setCredentials({ ...credentials, password: e.target.value })
                  }
                  required
                />
              </div>
            </div>

            {error && (
              <div className="p-3 rounded-md bg-red-50 border border-red-100 text-red-700 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-2"
            >
              {loading ? 'Ingresando...' : 'Iniciar sesión'}
            </button>
            <div className="text-center text-sm">
              <Link
                to="/recuperar-contrasena"
                className="font-medium text-primary-600 hover:text-primary-700"
              >
                ¿Olvidaste tu contraseña?
              </Link>
            </div>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-gray-500">
          © 2026 Plataforma Escolar. Todos los derechos reservados.
        </p>
      </div>
    </div>
  );
}