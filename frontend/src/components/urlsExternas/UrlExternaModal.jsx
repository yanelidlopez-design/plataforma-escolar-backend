import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { Plus, Edit, Globe, Clock, Link, Save } from 'lucide-react';
import Modal from '../common/Modal';

/**
 * UrlExternaModal - Modal para crear o editar una URL externa dinámica.
 * Campos: slug (código), nombre, fecha de expiración, estado activo/inactivo.
 *
 * Props:
 *  - isOpen: boolean
 *  - onClose: () => void
 *  - onSave: (data) => Promise<void>
 *  - url: object|null (si se está editando)
 */
export default function UrlExternaModal({ isOpen, onClose, onSave, url = null }) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({
    defaultValues: {
      nombre: '',
      fecha_inicio: '',
      fecha_fin: '',
      activo_manual: true,
    },
  });

  useEffect(() => {
    if (!isOpen) return;
    reset({
      nombre: url?.nombre ?? '',
      fecha_inicio: url?.fecha_inicio?.slice(0, 10) ?? '',
      fecha_fin: url?.fecha_fin?.slice(0, 10) ?? '',
      activo_manual: url?.activo_manual ?? true,
    });
  }, [isOpen, reset, url]);

  const onSubmit = (data) => onSave(data);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={url ? 'Editar URL Externa' : 'Registrar URL Externa'}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Nombre</label>
            <input
              {...register('nombre', { required: 'El nombre es obligatorio.' })}
              placeholder="Inscripciones Año Escolar"
              className="input-field"
            />
            {errors.nombre && <p className="text-xs text-red-600 mt-1">{errors.nombre.message}</p>}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Fecha de inicio</label>
              <input
                type="date"
                {...register('fecha_inicio')}
                className="input-field"
              />
              {errors.fecha_inicio && <p className="text-xs text-red-600 mt-1">{errors.fecha_inicio.message}</p>}
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Fecha de expiración</label>
              <input
                type="date"
                {...register('fecha_fin')}
                className="input-field"
              />
              {errors.fecha_fin && <p className="text-xs text-red-600 mt-1">{errors.fecha_fin.message}</p>}
              <p className="text-xs text-gray-500 mt-1">Fecha en que el formulario cierra automáticamente</p>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <input
              type="checkbox"
              {...register('activo_manual')}
              className="w-4 h-4 text-primary-600 rounded border-gray-300"
            />
            <label className="text-sm font-medium text-gray-700">
              URL activa (disponible públicamente)
            </label>
            {!url || url.activo_manual ? (
              <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">Activo</span>
            ) : (
              <span className="ml-2 text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">Inactivo</span>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-6 border-t border-gray-200">
          <button type="button" onClick={onClose} className="btn-secondary">
            Cancelar
          </button>
          <button type="submit" className="btn-primary flex items-center gap-2">
            <Save className="w-4 h-4" />
            {url ? 'Actualizar URL' : 'Crear URL'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
