import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Lock, Mail, ShieldAlert } from 'lucide-react';
import {
  confirmarRestablecimiento,
  solicitarRestablecimiento,
} from '../api/auth';

export default function RecuperarContrasena() {
  const [searchParams] = useSearchParams();
  const uid = searchParams.get('uid');
  const token = searchParams.get('token');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    try {
      if (token) {
        await confirmarRestablecimiento({
          uid,
          token,
          contrasena_nueva: password,
          confirmar_contrasena: confirmation,
        });
        setMessage('Tu contraseña fue actualizada. Ya puedes iniciar sesión.');
      } else {
        const response = await solicitarRestablecimiento(email);
        setMessage(response.data.detail);
      }
    } catch (requestError) {
      const responseData = requestError.response?.data;
      const detail = responseData?.detail
        || Object.values(responseData || {}).flat()[0]
        || 'No se pudo completar la solicitud. Intenta de nuevo.';
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center">
          <ShieldAlert className="mb-4 h-12 w-12 text-primary-600" />
          <h1 className="text-2xl font-bold text-gray-900">Plataforma Escolar</h1>
          <p className="text-sm text-gray-500">
            {token ? 'Crea una nueva contraseña' : 'Recupera el acceso a tu cuenta'}
          </p>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
          {message ? (
            <div className="space-y-5">
              <p className="rounded-md border border-green-100 bg-green-50 p-3 text-sm text-green-700">
                {message}
              </p>
              <Link to="/login" className="btn-primary block w-full py-2 text-center">
                Ir a iniciar sesión
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              {token ? (
                <>
                  <div>
                    <label htmlFor="password" className="mb-1 block text-sm font-medium text-gray-700">
                      Nueva contraseña
                    </label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                      <input
                        id="password"
                        type="password"
                        autoComplete="new-password"
                        className="input-field pl-10"
                        minLength={8}
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        required
                      />
                    </div>
                  </div>
                  <div>
                    <label htmlFor="confirmation" className="mb-1 block text-sm font-medium text-gray-700">
                      Confirmar contraseña
                    </label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                      <input
                        id="confirmation"
                        type="password"
                        autoComplete="new-password"
                        className="input-field pl-10"
                        minLength={8}
                        value={confirmation}
                        onChange={(event) => setConfirmation(event.target.value)}
                        required
                      />
                    </div>
                  </div>
                </>
              ) : (
                <div>
                  <label htmlFor="email" className="mb-1 block text-sm font-medium text-gray-700">
                    Correo asociado a tu cuenta
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                    <input
                      id="email"
                      type="email"
                      autoComplete="email"
                      className="input-field pl-10"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      required
                    />
                  </div>
                </div>
              )}

              {error && (
                <p className="rounded-md border border-red-100 bg-red-50 p-3 text-sm text-red-700">
                  {error}
                </p>
              )}

              <button type="submit" disabled={loading} className="btn-primary w-full py-2">
                {loading
                  ? 'Procesando...'
                  : token
                    ? 'Guardar nueva contraseña'
                    : 'Enviar enlace de recuperación'}
              </button>
            </form>
          )}
        </div>

        <Link
          to="/login"
          className="mt-6 flex items-center justify-center gap-2 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Volver al inicio de sesión
        </Link>
      </div>
    </div>
  );
}
