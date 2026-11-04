import { useEffect, useState } from 'react';
import { useFieldArray, useForm } from 'react-hook-form';
import { Plus, User, Briefcase, Building2, KeyRound } from 'lucide-react';
import Modal from '../common/Modal';
import { useAuth } from '../../context/AuthContext';
import { restablecerContrasenaPersonal } from '../../api/personal';

function describirErrorContrasena(error) {
  const data = error.response?.data;
  if (!data) return error.message || 'No se pudo restablecer la contraseña.';
  if (data.detail) return data.detail;
  return Object.values(data).flat().map(String).join(' ');
}

const VALORES_INICIALES = {
  primer_nombre: '', segundo_nombre: '', primer_apellido: '', segundo_apellido: '',
  cedula: '', telefono: '', correo: '', direccion: '',
  fecha_nacimiento: '', estado_civil: '', numero_hijos: '', hijos: [],
  cargo: 'Profesor', codigo_cargo: '', categoria: '',
  dependencia: '', codigo_dependencia: '', titulo: '', especialidad: '',
  fecha_ingreso_ministerio: '', fecha_ingreso_institucion: '',
  talla_zapato: '', talla_camisa: '', talla_pantalon: '',
};

function calcularAniosDesdeFecha(fecha) {
  if (!fecha) return '';
  const [año, mes, dia] = fecha.split('-').map(Number);
  if (!año || !mes || !dia) return '';
  const hoy = new Date();
  const edad = hoy.getFullYear() - año
    - (
      hoy.getMonth() + 1 < mes
      || (hoy.getMonth() + 1 === mes && hoy.getDate() < dia)
    );
  return edad >= 0 ? edad : '';
}

export default function PersonalModal({ isOpen, onClose, onSave, persona = null }) {
  const [activeTab, setActiveTab] = useState('personales');
  const [mostrarRestablecimiento, setMostrarRestablecimiento] = useState(false);
  const [contrasenaNueva, setContrasenaNueva] = useState('');
  const [confirmacionContrasena, setConfirmacionContrasena] = useState('');
  const [errorContrasena, setErrorContrasena] = useState('');
  const [exitoContrasena, setExitoContrasena] = useState('');
  const [restableciendo, setRestableciendo] = useState(false);
  const { user } = useAuth();
  const esAdministrador = user?.rol?.toLowerCase() === 'admin';

  const {
    register,
    handleSubmit,
    reset,
    watch,
    control,
    formState: { errors },
  } = useForm({
    defaultValues: VALORES_INICIALES,
  });

  const { fields: camposHijos, append: agregarHijos, remove: quitarHijos } = useFieldArray({
    control,
    name: 'hijos',
  });
  const fechaNacimiento = watch('fecha_nacimiento');
  const edad = calcularAniosDesdeFecha(fechaNacimiento);
  const numeroHijos = Number(watch('numero_hijos')) || 0;

  useEffect(() => {
    if (!isOpen) return;
    const valores = { ...VALORES_INICIALES };
    if (persona) {
      Object.keys(valores).forEach((campo) => {
        if (campo in persona) valores[campo] = persona[campo] ?? '';
      });
      valores.hijos = persona.hijos || [];
    }
    reset(valores);
    setActiveTab('personales');
    setMostrarRestablecimiento(false);
    setContrasenaNueva('');
    setConfirmacionContrasena('');
    setErrorContrasena('');
    setExitoContrasena('');
  }, [isOpen, persona, reset]);

  useEffect(() => {
    const cantidadDeseada = Math.max(0, numeroHijos);
    if (camposHijos.length < cantidadDeseada) {
      agregarHijos(
        Array.from({ length: cantidadDeseada - camposHijos.length }, () => ({
          primer_nombre: '',
          segundo_nombre: '',
          edad: '',
        })),
      );
    } else if (camposHijos.length > cantidadDeseada) {
      quitarHijos(
        Array.from(
          { length: camposHijos.length - cantidadDeseada },
          (_, index) => cantidadDeseada + index,
        ),
      );
    }
  }, [numeroHijos, camposHijos.length, agregarHijos, quitarHijos]);

  const onSubmit = (data) => onSave(data);

  const handleRestablecerContrasena = async () => {
    setErrorContrasena('');
    setExitoContrasena('');
    if (contrasenaNueva !== confirmacionContrasena) {
      setErrorContrasena('La confirmación no coincide con la nueva contraseña.');
      return;
    }

    setRestableciendo(true);
    try {
      const response = await restablecerContrasenaPersonal(persona.id_profesor, {
        contrasena_nueva: contrasenaNueva,
        confirmar_contrasena: confirmacionContrasena,
      });
      setExitoContrasena(response.data.detail);
      setContrasenaNueva('');
      setConfirmacionContrasena('');
    } catch (error) {
      setErrorContrasena(describirErrorContrasena(error));
    } finally {
      setRestableciendo(false);
    }
  };

  const CARGO_CHOICES = [
    { value: 'Integral', label: 'Integral' },
    { value: 'Profesor', label: 'Profesor' },
    { value: 'Obrero', label: 'Obrero' },
    { value: 'Cocinera', label: 'Cocinera' },
    { value: 'Administrativo', label: 'Administrativo' },
    { value: 'Director (Directivo)', label: 'Director (Directivo)' },
    { value: 'Sub-Director (Directivo)', label: 'Sub-Director (Directivo)' },
    { value: 'Coordinador (Directivo)', label: 'Coordinador (Directivo)' },
  ];

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={persona ? 'Editar Personal' : 'Registrar Personal'}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <div className="flex gap-4 border-b border-gray-200 pb-4">
          <button
            type="button"
            onClick={() => setActiveTab('personales')}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'personales' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <User className="w-4 h-4" /> Datos Personales
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('laborales')}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'laborales' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Briefcase className="w-4 h-4" /> Datos Laborales
          </button>
        </div>

        {activeTab === 'personales' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Primer Nombre</label>
                <input {...register('primer_nombre')} placeholder="Primer nombre" className="input-field" />
                {errors.primer_nombre && <p className="text-xs text-red-600">{errors.primer_nombre.message}</p>}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Segundo Nombre</label>
                <input {...register('segundo_nombre')} placeholder="Segundo nombre (opcional)" className="input-field" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Primer Apellido</label>
                <input {...register('primer_apellido')} placeholder="Primer apellido" className="input-field" />
                {errors.primer_apellido && <p className="text-xs text-red-600">{errors.primer_apellido.message}</p>}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Segundo Apellido</label>
                <input {...register('segundo_apellido')} placeholder="Segundo apellido (opcional)" className="input-field" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Cédula de Identidad</label>
                <input {...register('cedula')} placeholder="V-12345678" className="input-field" />
                {errors.cedula && <p className="text-xs text-red-600">{errors.cedula.message}</p>}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Teléfono</label>
                <input {...register('telefono')} placeholder="0412-1234567" className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Correo Electrónico</label>
                <input {...register('correo')} type="email" placeholder="correo@ejemplo.com" className="input-field" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Fecha de Nacimiento</label>
                <input type="date" {...register('fecha_nacimiento')} className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Edad</label>
                <input value={edad} readOnly aria-readonly="true" placeholder="Se calcula automáticamente" className="input-field bg-gray-50" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Estado Civil</label>
                <select {...register('estado_civil')} className="select-field">
                  <option value="">Seleccionar</option>
                  <option value="Soltero">Soltero</option>
                  <option value="Casado">Casado</option>
                  <option value="Divorciado">Divorciado</option>
                  <option value="Viudo">Viudo</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Número de Hijos</label>
                <input type="number" min="0" step="1" {...register('numero_hijos')} placeholder="0" className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Dirección</label>
                <input {...register('direccion')} placeholder="Dirección completa" className="input-field" />
              </div>
            </div>
            {camposHijos.length > 0 && (
              <section className="space-y-3 rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-800">Datos de los hijos</h3>
                {camposHijos.map((campo, index) => (
                  <div key={campo.id} className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-gray-700">
                        Hijo {index + 1}: primer nombre
                      </label>
                      <input
                        {...register(`hijos.${index}.primer_nombre`)}
                        placeholder="Primer nombre"
                        className="input-field"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-gray-700">
                        Segundo nombre
                      </label>
                      <input
                        {...register(`hijos.${index}.segundo_nombre`)}
                        placeholder="Segundo nombre (opcional)"
                        className="input-field"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-gray-700">
                        Edad
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="120"
                        {...register(`hijos.${index}.edad`)}
                        placeholder="Edad en años"
                        className="input-field"
                      />
                    </div>
                  </div>
                ))}
              </section>
            )}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Talla de Zapato</label>
                <input {...register('talla_zapato')} placeholder="Ej: 40" className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Talla de Camisa</label>
                <input {...register('talla_camisa')} placeholder="Ej: M" className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Talla de Pantalón</label>
                <input {...register('talla_pantalon')} placeholder="Ej: 38" className="input-field" />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'laborales' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Cargo</label>
                <select {...register('cargo')} className="select-field">
                  {CARGO_CHOICES.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Código de Cargo</label>
                <input {...register('codigo_cargo')} placeholder="Código de cargo" className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Categoría Jerárquica</label>
                <input
                  {...register('categoria')}
                  placeholder="Escribe la categoría jerárquica"
                  maxLength={50}
                  className="input-field"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Dependencia</label>
                <input {...register('dependencia')} placeholder="Dependencia" className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Código de Dependencia</label>
                <input {...register('codigo_dependencia')} placeholder="Código" className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Título</label>
                <input {...register('titulo')} placeholder="Título obtenido" className="input-field" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Especialidad</label>
                <input {...register('especialidad')} placeholder="Especialidad" className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Fecha Ingreso Ministerio</label>
                <input type="date" {...register('fecha_ingreso_ministerio')} className="input-field" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Fecha Ingreso Institución</label>
                <input type="date" {...register('fecha_ingreso_institucion')} className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Dirección</label>
                <input {...register('direccion')} placeholder="Dirección laboral" className="input-field" />
              </div>
            </div>
            <div className="pt-4 border-t border-gray-200">
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-3 flex items-center gap-2">
                <Building2 className="w-3 h-3" /> Información Adicional
              </h4>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Tiempo de servicio</label>
                <input
                  value={calcularAniosDesdeFecha(watch('fecha_ingreso_institucion'))}
                  readOnly
                  aria-readonly="true"
                  placeholder="Se calcula con la fecha de ingreso"
                  className="input-field bg-gray-50"
                />
              </div>
            </div>
          </div>
        )}

        {persona && esAdministrador && (
          <section className="border-t border-gray-200 pt-4">
            <button
              type="button"
              onClick={() => setMostrarRestablecimiento((visible) => !visible)}
              className="flex items-center gap-2 text-sm font-medium text-primary-700 hover:text-primary-800"
            >
              <KeyRound className="h-4 w-4" />
              {mostrarRestablecimiento ? 'Ocultar restablecimiento' : 'Restablecer contraseña de acceso'}
            </button>
            {mostrarRestablecimiento && (
              <div className="mt-4 space-y-3 rounded-lg bg-gray-50 p-4">
                <p className="text-sm text-gray-600">
                  Usuario: <strong>{persona.usuario_detalle?.nombre_usuario || 'Cuenta vinculada'}</strong>
                </p>
                <p className="text-xs text-gray-500">
                  La contraseña nueva no se muestra después de guardarla. Compártela de forma segura.
                </p>
                <div>
                  <label htmlFor="personal-contrasena-nueva" className="mb-1 block text-xs font-medium text-gray-700">
                    Nueva contraseña temporal
                  </label>
                  <input
                    id="personal-contrasena-nueva"
                    type="password"
                    autoComplete="new-password"
                    minLength={8}
                    required
                    value={contrasenaNueva}
                    onChange={(event) => setContrasenaNueva(event.target.value)}
                    className="input-field"
                  />
                </div>
                <div>
                  <label htmlFor="personal-confirmar-contrasena" className="mb-1 block text-xs font-medium text-gray-700">
                    Confirmar contraseña temporal
                  </label>
                  <input
                    id="personal-confirmar-contrasena"
                    type="password"
                    autoComplete="new-password"
                    minLength={8}
                    required
                    value={confirmacionContrasena}
                    onChange={(event) => setConfirmacionContrasena(event.target.value)}
                    className="input-field"
                  />
                </div>
                {errorContrasena && <p role="alert" className="text-sm text-red-600">{errorContrasena}</p>}
                {exitoContrasena && <p role="status" className="text-sm text-green-700">{exitoContrasena}</p>}
                <button
                  type="button"
                  onClick={handleRestablecerContrasena}
                  disabled={restableciendo || !contrasenaNueva || !confirmacionContrasena}
                  className="btn-primary disabled:opacity-60"
                >
                  {restableciendo ? 'Guardando...' : 'Guardar nueva contraseña'}
                </button>
              </div>
            )}
          </section>
        )}

        <div className="flex justify-end gap-3 pt-6 border-t border-gray-200">
          <button type="button" onClick={onClose} className="btn-secondary">
            Cancelar
          </button>
          <button type="submit" className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />
            {persona ? 'Actualizar' : 'Guardar Personal'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
