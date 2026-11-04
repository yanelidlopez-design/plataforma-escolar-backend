import { useState } from 'react';
import Modal from './Modal';
import { cambiarContrasena } from '../../api/auth';

function describirError(error) {
  const data = error.response?.data;
  if (!data) return error.message || 'No se pudo actualizar la contraseña.';
  if (data.detail) return data.detail;
  return Object.values(data)
    .flat()
    .map(String)
    .join(' ');
}

export default function PasswordChangeModal({ isOpen, onClose }) {
  const [values, setValues] = useState({
    contrasena_actual: '',
    contrasena_nueva: '',
    confirmar_contrasena: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [saving, setSaving] = useState(false);

  const updateValue = (event) => {
    setValues((current) => ({ ...current, [event.target.name]: event.target.value }));
    setError('');
    setSuccess('');
  };

  const handleClose = () => {
    setValues({ contrasena_actual: '', contrasena_nueva: '', confirmar_contrasena: '' });
    setError('');
    setSuccess('');
    onClose();
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    if (values.contrasena_nueva !== values.confirmar_contrasena) {
      setError('La confirmación no coincide con la nueva contraseña.');
      return;
    }

    setSaving(true);
    try {
      const response = await cambiarContrasena(values);
      setSuccess(response.data.detail);
      setValues({ contrasena_actual: '', contrasena_nueva: '', confirmar_contrasena: '' });
    } catch (requestError) {
      setError(describirError(requestError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Cambiar contraseña">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="contrasena_actual" className="mb-1 block text-sm font-medium text-gray-700">
            Contraseña actual
          </label>
          <input
            id="contrasena_actual"
            name="contrasena_actual"
            type="password"
            autoComplete="current-password"
            required
            value={values.contrasena_actual}
            onChange={updateValue}
            className="input-field"
          />
        </div>
        <div>
          <label htmlFor="contrasena_nueva" className="mb-1 block text-sm font-medium text-gray-700">
            Nueva contraseña
          </label>
          <input
            id="contrasena_nueva"
            name="contrasena_nueva"
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
            value={values.contrasena_nueva}
            onChange={updateValue}
            className="input-field"
          />
        </div>
        <div>
          <label htmlFor="confirmar_contrasena" className="mb-1 block text-sm font-medium text-gray-700">
            Confirmar nueva contraseña
          </label>
          <input
            id="confirmar_contrasena"
            name="confirmar_contrasena"
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
            value={values.confirmar_contrasena}
            onChange={updateValue}
            className="input-field"
          />
        </div>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        {success && <p role="status" className="text-sm text-green-700">{success}</p>}
        <div className="flex justify-end gap-3 border-t border-gray-200 pt-4">
          <button type="button" onClick={handleClose} className="btn-secondary">Cerrar</button>
          <button type="submit" disabled={saving} className="btn-primary disabled:opacity-60">
            {saving ? 'Actualizando...' : 'Actualizar contraseña'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
