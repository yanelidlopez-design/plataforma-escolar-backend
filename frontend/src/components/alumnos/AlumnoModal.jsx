import { useEffect, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { Plus, User, GraduationCap, Building2, MapPin } from 'lucide-react';
import Modal from '../common/Modal';

const VALORES_INICIALES = {
  primer_nombre: '', segundo_nombre: '', primer_apellido: '', segundo_apellido: '',
  tipo_documento_identidad: 'C.I.', numero_documento_identidad: '', cedula_escolar: '',
  fecha_nacimiento: '', genero: '', lugar_nacimiento: '', nacionalidad: '',
  entidad_federal_nacimiento: '', municipio_nacimiento: '', parroquia_nacimiento: '',
  carnet_patria_codigo: '', carnet_patria_serial: '',
  numero_cuenta: '', tipo_cuenta: '', banco: '',
  grupo_sanguineo: '', condicion_fisica: '', alergico_a: '', tratamiento_medico: '',
  peso_kg: '', talla_cm: '', apoyo_escolar: false, vacunas_completas: false,
  discapacidad: false, tipo_discapacidad: '',
  calle: '', ciudad: '', estado: '', referencia: '',
  talla_camisa: '', talla_pantalon: '', talla_zapato: '',
  estado_civil_padres: '', ingreso_familiar: '', profesion_madre: '', profesion_padre: '',
  tipo_vivienda: '', numero_hermanos: '', numero_en_el_planter: '', observaciones: '',
  fecha_inscripcion_inicial: '', fecha_egreso: '', estatus_general: 'Activo',
  id_grupo: '', id_profesor_encargado: '',
  representante_cedula: '', representante_nombre: '',
  representante_telefono: '', parentesco: 'Padre',
};

function calcularEdad(fechaNacimiento) {
  if (!fechaNacimiento) return '';
  const [año, mes, dia] = fechaNacimiento.split('-').map(Number);
  if (!año || !mes || !dia) return '';

  const hoy = new Date();
  let edad = hoy.getFullYear() - año;
  if (
    hoy.getMonth() + 1 < mes
    || (hoy.getMonth() + 1 === mes && hoy.getDate() < dia)
  ) {
    edad -= 1;
  }
  return edad >= 0 ? edad : '';
}

export default function AlumnoModal({
  isOpen,
  onClose,
  onSave,
  alumno = null,
  grupos = [],
  profesores = [],
}) {
  const [activeTab, setActiveTab] = useState('personales');

  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors },
  } = useForm({
    defaultValues: VALORES_INICIALES,
  });
  const fechaNacimiento = useWatch({ control, name: 'fecha_nacimiento' });
  const edad = calcularEdad(fechaNacimiento);

  useEffect(() => {
    if (!isOpen) return;
    const valores = { ...VALORES_INICIALES };
    if (alumno) {
      Object.keys(valores).forEach((campo) => {
        if (campo in alumno) valores[campo] = alumno[campo] ?? '';
      });
      valores.id_grupo = alumno.grupo_inscripcion_id ?? '';
      valores.representante_cedula = alumno.representante?.cedula ?? '';
      valores.representante_nombre = alumno.representante?.nombre ?? '';
      valores.representante_telefono = alumno.representante?.telefono ?? '';
      valores.parentesco = alumno.parentesco || 'Padre';
      valores.calle = alumno.direccion?.calle ?? '';
      valores.ciudad = alumno.direccion?.ciudad ?? '';
      valores.estado = alumno.direccion?.estado ?? '';
      valores.referencia = alumno.direccion?.referencia ?? '';
    }
    reset(valores);
    setActiveTab('personales');
  }, [alumno, isOpen, reset]);

  const onSubmit = (data) => onSave(data);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={alumno ? 'Editar Alumno' : 'Registrar Alumno'}>
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
            onClick={() => setActiveTab('academicos')}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'academicos' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <GraduationCap className="w-4 h-4" /> Datos Académicos
          </button>
        </div>

        {activeTab === 'personales' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="col-span-1 md:col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">Nombres</label>
                <input {...register('primer_nombre')} placeholder="Primer nombre" className="input-field" />
                {errors.primer_nombre && <p className="text-xs text-red-600">{errors.primer_nombre.message}</p>}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Segundo nombre</label>
                <input {...register('segundo_nombre')} placeholder="Segundo nombre (opcional)" className="input-field" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="col-span-1 md:col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">Apellidos</label>
                <input {...register('primer_apellido')} placeholder="Primer apellido" className="input-field" />
                {errors.primer_apellido && <p className="text-xs text-red-600">{errors.primer_apellido.message}</p>}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Segundo apellido</label>
                <input {...register('segundo_apellido')} placeholder="Segundo apellido (opcional)" className="input-field" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Tipo de documento</label>
                <select {...register('tipo_documento_identidad')} className="select-field">
                  <option value="C.I.">Cédula de Identidad</option>
                  <option value="Pasaporte">Pasaporte</option>
                  <option value="Acta de Nacimiento">Acta de Nacimiento</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Número de documento</label>
                <input {...register('numero_documento_identidad')} placeholder="V-12345678" className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Cédula escolar</label>
                <input {...register('cedula_escolar')} placeholder="Cédula escolar" className="input-field" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Código del Carnet de la Patria</label>
                <input {...register('carnet_patria_codigo')} className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Serial del Carnet de la Patria</label>
                <input {...register('carnet_patria_serial')} className="input-field" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Fecha de nacimiento</label>
                <input type="date" {...register('fecha_nacimiento')} className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Edad</label>
                <input
                  type="number"
                  value={edad}
                  readOnly
                  aria-readonly="true"
                  placeholder="Se calcula automáticamente"
                  className="input-field bg-gray-50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Género</label>
                <select {...register('genero')} className="select-field">
                  <option value="Masculino">Masculino</option>
                  <option value="Femenino">Femenino</option>
                  <option value="Otro">Otro</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Nacionalidad</label>
                <input {...register('nacionalidad')} placeholder="Venezolano" className="input-field" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Grupo sanguíneo</label>
                <select {...register('grupo_sanguineo')} className="select-field">
                  <option value="">Seleccionar</option>
                  <option value="O+">O+</option><option value="O-">O-</option>
                  <option value="A+">A+</option><option value="A-">A-</option>
                  <option value="B+">B+</option><option value="B-">B-</option>
                  <option value="AB+">AB+</option><option value="AB-">AB-</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Lugar de nacimiento</label>
                <input {...register('lugar_nacimiento')} placeholder="Ciudad, estado" className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Estado de nacimiento</label>
                <input {...register('entidad_federal_nacimiento')} className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Municipio de nacimiento</label>
                <input {...register('municipio_nacimiento')} className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Parroquia de nacimiento</label>
                <input {...register('parroquia_nacimiento')} className="input-field" />
              </div>
            </div>
            <div className="pt-4 border-t border-gray-200">
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-3 flex items-center gap-2">
                <MapPin className="w-3 h-3" /> Dirección de residencia
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Calle / Avenida</label>
                  <input {...register('calle')} placeholder="Calle o avenida" className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Ciudad</label>
                  <input {...register('ciudad')} placeholder="Ciudad" className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Estado</label>
                  <input {...register('estado')} placeholder="Estado" className="input-field" />
                </div>
              </div>
              <div className="mt-3">
                <label className="block text-xs font-medium text-gray-700 mb-1">Referencia</label>
                <input {...register('referencia')} placeholder="Referencia (opcional)" className="input-field" />
              </div>
            </div>
            <div className="space-y-3 border-t border-gray-200 pt-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase">Datos médicos</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Condición física</label>
                  <input {...register('condicion_fisica')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Peso (kg)</label>
                  <input type="number" step="0.01" min="0" {...register('peso_kg')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Talla (cm)</label>
                  <input type="number" step="0.01" min="0" {...register('talla_cm')} className="input-field" />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Alergias</label>
                  <textarea {...register('alergico_a')} rows={2} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Tratamiento médico</label>
                  <textarea {...register('tratamiento_medico')} rows={2} className="input-field" />
                </div>
              </div>
              <div className="flex flex-wrap gap-6">
              <div className="flex items-center gap-2">
                <input type="checkbox" {...register('apoyo_escolar')} className="w-4 h-4 text-primary-600 rounded border-gray-300" />
                <label className="text-sm text-gray-700">Requiere apoyo escolar</label>
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" {...register('vacunas_completas')} className="w-4 h-4 text-primary-600 rounded border-gray-300" />
                <label className="text-sm text-gray-700">Vacunas completas</label>
              </div>
                <div className="flex items-center gap-2">
                  <input type="checkbox" {...register('discapacidad')} className="w-4 h-4 text-primary-600 rounded border-gray-300" />
                  <label className="text-sm text-gray-700">Tiene discapacidad</label>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Tipo de discapacidad</label>
                <textarea {...register('tipo_discapacidad')} rows={2} className="input-field" />
              </div>
            </div>
            <div className="space-y-3 border-t border-gray-200 pt-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase">Datos económicos y socioeconómicos</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Ingreso familiar</label>
                  <input type="number" step="0.01" min="0" {...register('ingreso_familiar')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Número de cuenta</label>
                  <input {...register('numero_cuenta')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Tipo de cuenta</label>
                  <input {...register('tipo_cuenta')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Banco</label>
                  <input {...register('banco')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Tipo de vivienda</label>
                  <input {...register('tipo_vivienda')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Profesión de la madre</label>
                  <input {...register('profesion_madre')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Profesión del padre</label>
                  <input {...register('profesion_padre')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Estado civil de los padres</label>
                  <input {...register('estado_civil_padres')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Número de hermanos</label>
                  <input type="number" min="0" step="1" {...register('numero_hermanos')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Número en el plantel</label>
                  <input type="number" min="0" step="1" {...register('numero_en_el_planter')} className="input-field" />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Talla de camisa</label>
                  <input {...register('talla_camisa')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Talla de pantalón</label>
                  <input {...register('talla_pantalon')} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Talla de zapato</label>
                  <input {...register('talla_zapato')} className="input-field" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Observaciones</label>
                <textarea {...register('observaciones')} rows={3} className="input-field" />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'academicos' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Grado / Grupo académico</label>
                <select {...register('id_grupo')} className="select-field">
                  <option value="">Seleccionar grupo</option>
                  {grupos.map((grupo) => (
                    <option key={grupo.id_grupo} value={grupo.id_grupo}>
                      {[
                        grupo.grado_detalle?.nombre_grado,
                        grupo.seccion_detalle?.nombre_seccion,
                        grupo.periodo_detalle?.nombre_periodo,
                      ].filter(Boolean).join(' - ')}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Profesor encargado</label>
                <select {...register('id_profesor_encargado')} className="select-field">
                  <option value="">Seleccionar profesor</option>
                  {profesores.map((profesor) => (
                    <option key={profesor.id_profesor} value={profesor.id_profesor}>
                      {[
                        profesor.primer_nombre,
                        profesor.segundo_nombre,
                        profesor.primer_apellido,
                        profesor.segundo_apellido,
                      ].filter(Boolean).join(' ')}
                      {profesor.cargo ? ` - ${profesor.cargo}` : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Estado del alumno</label>
                <select {...register('estatus_general')} className="select-field">
                  <option value="Activo">Activo</option>
                  <option value="Egresado">Egresado</option>
                  <option value="Retirado">Retirado</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Fecha de inscripción inicial</label>
                <input type="date" {...register('fecha_inscripcion_inicial')} className="input-field" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Fecha de egreso o retiro</label>
                <input type="date" {...register('fecha_egreso')} className="input-field" />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" {...register('repitiente')} className="w-4 h-4 text-primary-600 rounded border-gray-300" />
              <label className="text-sm text-gray-700">Alumno repitiente</label>
            </div>
            <div className="pt-4 border-t border-gray-200">
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-3 flex items-center gap-2">
                <Building2 className="w-3 h-3" /> Representante Legal
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Cédula del representante</label>
                  <input {...register('representante_cedula')} placeholder="V-12345678" className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Nombre completo</label>
                  <input {...register('representante_nombre')} placeholder="Nombres y apellidos" className="input-field" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Teléfono</label>
                  <input {...register('representante_telefono')} placeholder="0412-1234567" className="input-field" />
                </div>
              </div>
              <div className="mt-3">
                <label className="block text-xs font-medium text-gray-700 mb-1">Parentesco</label>
                <select {...register('parentesco')} className="select-field">
                  <option value="Padre">Padre</option>
                  <option value="Madre">Madre</option>
                  <option value="Representante">Representante</option>
                  <option value="Tutor">Tutor</option>
                </select>
              </div>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-6 border-t border-gray-200">
          <button type="button" onClick={onClose} className="btn-secondary">
            Cancelar
          </button>
          <button type="submit" className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />
            {alumno ? 'Actualizar' : 'Guardar Alumno'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
