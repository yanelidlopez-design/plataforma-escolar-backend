import { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Clock,
  CheckCircle,
  AlertCircle,
  Calendar,
  Users,
  Check,
  X,
  HelpCircle,
  Save,
  RotateCcw,
  School,
  ArrowLeft,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { toast } from 'react-toastify';
import UrlCerradaView from '../components/urlsExternas/UrlCerradaView';
import {
  getAsistenciaPublicaToken,
  getGruposAsistenciaPublica,
  getAlumnosAsistenciaPublica,
  registrarAsistenciaPublica,
} from '../api/asistenciaPublica';

/**
 * AsistenciaPublica - Página interactiva y responsive para el registro diario
 * de asistencia de estudiantes por enlace público tokenizado.
 */
export default function AsistenciaPublica() {
  const { token, slug } = useParams();
  const tokenValue = token || slug;

  // Estado de validación del enlace
  const [verificando, setVerificando] = useState(true);
  const [enlaceConfig, setEnlaceConfig] = useState(null);
  const [errorValidacion, setErrorValidacion] = useState(null);

  // Estado de grupos académicos
  const [grupos, setGrupos] = useState([]);
  const [cargandoGrupos, setCargandoGrupos] = useState(false);
  const [grupoSeleccionado, setGrupoSeleccionado] = useState(null);

  // Estado de estudiantes y asistencias
  const [alumnos, setAlumnos] = useState([]);
  const [cargandoAlumnos, setCargandoAlumnos] = useState(false);
  const [asistencias, setAsistencias] = useState({}); // { [id_alumno]: { estado: 'P'|'A'|'J', observaciones: '' } }
  const [filtroNombre, setFiltroNombre] = useState('');

  // Estado de envío
  const [guardando, setGuardando] = useState(false);
  const [guardadoExitoso, setGuardadoExitoso] = useState(false);
  const [resultadoGuardado, setResultadoGuardado] = useState(null);

  // 1. Validar el token y cargar configuración del enlace
  useEffect(() => {
    let mounted = true;
    const verificarToken = async () => {
      try {
        setVerificando(true);
        const resp = await getAsistenciaPublicaToken(tokenValue);
        if (!mounted) return;
        setEnlaceConfig(resp.data);
        setErrorValidacion(null);
      } catch (err) {
        if (!mounted) return;
        console.error('Error al verificar URL de asistencia pública:', err);
        setEnlaceConfig(null);
        setErrorValidacion(err.response?.data?.detail || 'Enlace de asistencia no válido o cerrado.');
      } finally {
        if (mounted) setVerificando(false);
      }
    };

    if (tokenValue) {
      verificarToken();
    } else {
      setVerificando(false);
      setErrorValidacion('Token de asistencia no proporcionado.');
    }

    return () => {
      mounted = false;
    };
  }, [tokenValue]);

  // 2. Al validar el token con éxito, cargar los grupos académicos
  useEffect(() => {
    if (!enlaceConfig || !enlaceConfig.activo) return;

    let mounted = true;
    const cargarGrupos = async () => {
      try {
        setCargandoGrupos(true);
        const res = await getGruposAsistenciaPublica(tokenValue);
        if (!mounted) return;
        const gruposData = Array.isArray(res.data) ? res.data : [];
        setGrupos(gruposData);
      } catch (err) {
        if (!mounted) return;
        console.error('Error al cargar grupos:', err);
        toast.error('No se pudieron cargar los grados y secciones disponibles.');
      } finally {
        if (mounted) setCargandoGrupos(false);
      }
    };

    cargarGrupos();

    return () => {
      mounted = false;
    };
  }, [enlaceConfig, tokenValue]);

  // 3. Al seleccionar un grupo, cargar la lista de alumnos
  const handleSeleccionarGrupo = async (grupo) => {
    setGrupoSeleccionado(grupo);
    setGuardadoExitoso(false);
    setResultadoGuardado(null);
    setFiltroNombre('');

    try {
      setCargandoAlumnos(true);
      const res = await getAlumnosAsistenciaPublica(tokenValue, grupo.id_grupo);
      const listaAlumnos = Array.isArray(res.data) ? res.data : [];
      setAlumnos(listaAlumnos);

      // Inicializar por defecto todos los alumnos como "Presente" (P)
      const initialMap = {};
      listaAlumnos.forEach((alumno) => {
        initialMap[alumno.id_alumno] = {
          estado: 'P',
          observaciones: '',
        };
      });
      setAsistencias(initialMap);
    } catch (err) {
      console.error('Error al cargar alumnos del grupo:', err);
      toast.error('Error al cargar la lista de alumnos del grupo.');
      setAlumnos([]);
    } finally {
      setCargandoAlumnos(false);
    }
  };

  // Cambiar el estado de un alumno individual ('P' | 'A' | 'J')
  const handleCambiarEstado = (idAlumno, nuevoEstado) => {
    setAsistencias((prev) => ({
      ...prev,
      [idAlumno]: {
        ...prev[idAlumno],
        estado: nuevoEstado,
      },
    }));
  };

  // Marcar a todos los alumnos con un estado rápido
  const handleMarcarTodos = (estado) => {
    setAsistencias((prev) => {
      const next = { ...prev };
      alumnos.forEach((a) => {
        next[a.id_alumno] = {
          ...next[a.id_alumno],
          estado,
        };
      });
      return next;
    });
  };

  // Guardar la asistencia
  const handleGuardarAsistencia = async () => {
    if (!grupoSeleccionado) {
      toast.warning('Por favor seleccione un grupo.');
      return;
    }

    if (alumnos.length === 0) {
      toast.info('No hay alumnos inscritos en este grupo para registrar.');
      return;
    }

    const fechaAsistencia =
      enlaceConfig?.fecha_dia || new Date().toISOString().slice(0, 10);

    const payloadAsistencias = alumnos.map((alumno) => {
      const reg = asistencias[alumno.id_alumno] || { estado: 'P' };
      return {
        id_alumno: alumno.id_alumno,
        estado: reg.estado || 'P',
        fecha: fechaAsistencia,
      };
    });

    try {
      setGuardando(true);
      const res = await registrarAsistenciaPublica(tokenValue, {
        grupo_id: grupoSeleccionado.id_grupo,
        asistencias: payloadAsistencias,
      });

      setResultadoGuardado(res.data);
      setGuardadoExitoso(true);
      toast.success('¡Asistencia registrada con éxito!');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      console.error('Error al registrar asistencia:', err);
      const msg =
        err.response?.data?.detail ||
        'Error al guardar la asistencia. Verifique su conexión y reintente.';
      toast.error(msg);
    } finally {
      setGuardando(false);
    }
  };

  // Filtrado de alumnos por nombre o cédula
  const alumnosFiltrados = useMemo(() => {
    if (!filtroNombre.trim()) return alumnos;
    const term = filtroNombre.toLowerCase();
    return alumnos.filter(
      (a) =>
        a.nombre_completo?.toLowerCase().includes(term) ||
        a.numero_documento?.toLowerCase().includes(term) ||
        a.cedula_escolar?.toLowerCase().includes(term),
    );
  }, [alumnos, filtroNombre]);

  // Contadores de estado
  const metricas = useMemo(() => {
    let p = 0;
    let a = 0;
    let j = 0;
    Object.values(asistencias).forEach((item) => {
      if (item.estado === 'P') p++;
      else if (item.estado === 'A') a++;
      else if (item.estado === 'J') j++;
    });
    return { presentes: p, ausentes: a, justificados: j, total: alumnos.length };
  }, [asistencias, alumnos]);

  // Formato legible de fecha
  const fechaLegible = useMemo(() => {
    const rawFecha = enlaceConfig?.fecha_dia;
    if (!rawFecha) {
      return new Date().toLocaleDateString('es-ES', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    }
    try {
      const d = new Date(rawFecha.includes('T') ? rawFecha : `${rawFecha}T12:00:00`);
      return d.toLocaleDateString('es-ES', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch {
      return rawFecha;
    }
  }, [enlaceConfig]);

  // Render: Cargando verificación
  if (verificando) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
        <div className="text-center p-8 bg-white rounded-2xl shadow-sm border border-slate-200 max-w-sm w-full">
          <Clock className="w-10 h-10 text-blue-600 mb-3 animate-spin mx-auto" />
          <h2 className="text-base font-semibold text-slate-800">Verificando enlace</h2>
          <p className="text-xs text-slate-500 mt-1">
            Validando acceso al registro de asistencia diaria...
          </p>
        </div>
      </div>
    );
  }

  // Render: Enlace cerrado o inválido
  if (!enlaceConfig || !enlaceConfig.activo || errorValidacion) {
    return <UrlCerradaView mensaje={errorValidacion} />;
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 antialiased pb-20">
      {/* Encabezado Principal */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-xs">
        <div className="max-w-4xl mx-auto px-4 py-3.5 sm:py-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-sm shrink-0">
              <School className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-100">
                  Pase de Asistencia
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  Enlace Activo
                </span>
              </div>
              <h1 className="text-base sm:text-lg font-bold text-slate-900 truncate mt-0.5">
                {enlaceConfig.nombre_institucion || 'Registro de Asistencia Diaria'}
              </h1>
            </div>
          </div>

          <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-600 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200">
            <Calendar className="w-3.5 h-3.5 text-slate-500" />
            <span className="capitalize">{fechaLegible}</span>
          </div>
        </div>

        {/* Sub-barra de fecha en móviles */}
        <div className="sm:hidden px-4 py-1.5 bg-slate-100 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600">
          <span className="flex items-center gap-1.5 capitalize truncate">
            <Calendar className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            {fechaLegible}
          </span>
          {grupoSeleccionado && (
            <span className="font-semibold text-blue-700 truncate ml-2">
              {grupoSeleccionado.grado} {grupoSeleccionado.seccion}
            </span>
          )}
        </div>
      </header>

      {/* Contenido Principal */}
      <main className="max-w-4xl mx-auto px-4 py-6">
        {/* Banner de Confirmación de Guardado */}
        {guardadoExitoso && (
          <div className="mb-6 p-4 sm:p-5 bg-emerald-50 border border-emerald-200 rounded-2xl shadow-xs">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-full bg-emerald-600 text-white flex items-center justify-center shrink-0">
                <Check className="w-5 h-5 stroke-[2.5]" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm sm:text-base font-bold text-emerald-900">
                  ¡Asistencia Registrada Correctamente!
                </h3>
                <p className="text-xs sm:text-sm text-emerald-700 mt-0.5">
                  Los registros de asistencia para el grupo{' '}
                  <strong>
                    {grupoSeleccionado?.grado} - Sección {grupoSeleccionado?.seccion}
                  </strong>{' '}
                  han sido guardados en el sistema escolar.
                </p>

                {resultadoGuardado && (
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="bg-emerald-100 text-emerald-800 px-2.5 py-1 rounded-md font-medium">
                      Nuevos: {resultadoGuardado.creados ?? 0}
                    </span>
                    <span className="bg-emerald-100 text-emerald-800 px-2.5 py-1 rounded-md font-medium">
                      Actualizados: {resultadoGuardado.actualizados ?? 0}
                    </span>
                    {resultadoGuardado.errores?.length > 0 && (
                      <span className="bg-rose-100 text-rose-800 px-2.5 py-1 rounded-md font-medium">
                        Alertas: {resultadoGuardado.errores.length}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Paso 1: Selección de Grado y Sección */}
        <section className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold">
                1
              </span>
              <h2 className="text-sm sm:text-base font-bold text-slate-900">
                Selecciona Grado y Sección
              </h2>
            </div>
            {grupoSeleccionado && (
              <button
                onClick={() => setGrupoSeleccionado(null)}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium inline-flex items-center gap-1"
              >
                <RotateCcw className="w-3 h-3" /> Cambiar grupo
              </button>
            )}
          </div>

          {cargandoGrupos ? (
            <div className="p-8 text-center bg-white rounded-xl border border-slate-200">
              <Clock className="w-6 h-6 text-blue-600 animate-spin mx-auto mb-2" />
              <p className="text-xs text-slate-500">Cargando grados y secciones...</p>
            </div>
          ) : grupos.length === 0 ? (
            <div className="p-6 bg-amber-50 rounded-xl border border-amber-200 text-amber-800 text-xs sm:text-sm flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
              <span>No se encontraron grupos académicos configurados para el registro.</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
              {grupos.map((g) => {
                const isSelected = grupoSeleccionado?.id_grupo === g.id_grupo;
                return (
                  <button
                    key={g.id_grupo}
                    type="button"
                    onClick={() => handleSeleccionarGrupo(g)}
                    className={`w-full text-left p-3.5 rounded-xl border transition-all flex items-center justify-between gap-3 ${
                      isSelected
                        ? 'bg-blue-600 text-white border-blue-600 shadow-sm ring-2 ring-blue-300'
                        : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-800 hover:border-slate-300'
                    }`}
                  >
                    <div className="min-w-0">
                      <div
                        className={`text-sm font-bold truncate ${
                          isSelected ? 'text-white' : 'text-slate-900'
                        }`}
                      >
                        {g.grado} - {g.seccion}
                      </div>
                      <div
                        className={`text-xs mt-0.5 truncate ${
                          isSelected ? 'text-blue-100' : 'text-slate-500'
                        }`}
                      >
                        Turno: {g.turno || 'Sin turno'}
                      </div>
                    </div>
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                        isSelected
                          ? 'bg-blue-500 text-white'
                          : 'bg-slate-100 text-slate-400'
                      }`}
                    >
                      <ChevronRight className="w-4 h-4" />
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </section>

        {/* Paso 2: Listado y Toma de Asistencia */}
        {grupoSeleccionado && (
          <section className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
            {/* Cabecera del Grupo Seleccionado */}
            <div className="p-4 sm:p-5 bg-gradient-to-r from-slate-900 to-slate-800 text-white">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase font-semibold text-blue-300 tracking-wider">
                    Paso 2 • Pase de Lista
                  </div>
                  <h3 className="text-lg sm:text-xl font-bold mt-0.5">
                    {grupoSeleccionado.grado} — Sección {grupoSeleccionado.seccion}
                  </h3>
                  <p className="text-xs text-slate-300 mt-0.5">
                    Turno {grupoSeleccionado.turno} • {alumnos.length} estudiantes inscritos
                  </p>
                </div>

                {/* Acciones Rápidas */}
                <div className="flex items-center gap-2 pt-2 sm:pt-0 border-t border-slate-700 sm:border-0">
                  <button
                    type="button"
                    onClick={() => handleMarcarTodos('P')}
                    className="flex-1 sm:flex-none text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-medium px-3 py-1.5 rounded-lg transition flex items-center justify-center gap-1.5"
                    title="Marcar todos como Presentes"
                  >
                    <Check className="w-3.5 h-3.5" /> Todos Presentes
                  </button>
                  <button
                    type="button"
                    onClick={() => handleMarcarTodos('A')}
                    className="flex-1 sm:flex-none text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 font-medium px-3 py-1.5 rounded-lg transition flex items-center justify-center gap-1.5"
                    title="Marcar todos como Ausentes"
                  >
                    <X className="w-3.5 h-3.5" /> Todos Ausentes
                  </button>
                </div>
              </div>

              {/* Barra de Resumen en Tiempo Real */}
              <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-slate-700 text-center text-xs">
                <div className="bg-slate-800/80 rounded-lg p-2 border border-slate-700">
                  <span className="text-emerald-400 font-bold text-sm block">
                    {metricas.presentes}
                  </span>
                  <span className="text-slate-400 text-[11px]">Presentes</span>
                </div>
                <div className="bg-slate-800/80 rounded-lg p-2 border border-slate-700">
                  <span className="text-rose-400 font-bold text-sm block">
                    {metricas.ausentes}
                  </span>
                  <span className="text-slate-400 text-[11px]">Ausentes</span>
                </div>
                <div className="bg-slate-800/80 rounded-lg p-2 border border-slate-700">
                  <span className="text-amber-400 font-bold text-sm block">
                    {metricas.justificados}
                  </span>
                  <span className="text-slate-400 text-[11px]">Justificados</span>
                </div>
              </div>
            </div>

            {/* Buscador dentro del grupo */}
            <div className="p-3.5 sm:p-4 bg-slate-50 border-b border-slate-200">
              <input
                type="text"
                placeholder="Buscar alumno por nombre o documento..."
                value={filtroNombre}
                onChange={(e) => setFiltroNombre(e.target.value)}
                className="w-full text-xs sm:text-sm bg-white border border-slate-300 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-2xs"
              />
            </div>

            {/* Lista de Alumnos */}
            <div className="p-3.5 sm:p-5">
              {cargandoAlumnos ? (
                <div className="py-12 text-center">
                  <Clock className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-2" />
                  <p className="text-xs sm:text-sm text-slate-500">
                    Cargando nómina de alumnos...
                  </p>
                </div>
              ) : alumnos.length === 0 ? (
                <div className="py-12 text-center text-slate-500 text-xs sm:text-sm">
                  <Users className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  No hay alumnos activos registrados en este grupo.
                </div>
              ) : alumnosFiltrados.length === 0 ? (
                <div className="py-8 text-center text-slate-500 text-xs sm:text-sm">
                  No se encontraron alumnos con el criterio de búsqueda "{filtroNombre}".
                </div>
              ) : (
                <div className="space-y-2.5">
                  {alumnosFiltrados.map((alumno, idx) => {
                    const reg = asistencias[alumno.id_alumno] || { estado: 'P' };
                    const estadoActual = reg.estado;

                    return (
                      <div
                        key={alumno.id_alumno}
                        className={`p-3 sm:p-3.5 rounded-xl border transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                          estadoActual === 'P'
                            ? 'bg-emerald-50/50 border-emerald-200/80'
                            : estadoActual === 'A'
                            ? 'bg-rose-50/50 border-rose-200/80'
                            : 'bg-amber-50/50 border-amber-200/80'
                        }`}
                      >
                        {/* Info del Estudiante */}
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="w-6 text-center text-xs font-semibold text-slate-400 shrink-0">
                            {idx + 1}
                          </span>
                          <div className="min-w-0">
                            <div className="text-sm font-bold text-slate-900 truncate">
                              {alumno.nombre_completo}
                            </div>
                            <div className="text-xs text-slate-500 truncate mt-0.5">
                              {alumno.numero_documento
                                ? `Doc: ${alumno.numero_documento}`
                                : alumno.cedula_escolar
                                ? `Céd. Escolar: ${alumno.cedula_escolar}`
                                : 'Sin identificación registrada'}
                            </div>
                          </div>
                        </div>

                        {/* Botones de Selección Táctil de Asistencia */}
                        <div className="flex items-center gap-1.5 self-end sm:self-center shrink-0">
                          {/* Presente */}
                          <button
                            type="button"
                            onClick={() => handleCambiarEstado(alumno.id_alumno, 'P')}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1 ${
                              estadoActual === 'P'
                                ? 'bg-emerald-600 text-white shadow-xs'
                                : 'bg-white text-slate-600 border border-slate-200 hover:bg-emerald-50 hover:text-emerald-700'
                            }`}
                          >
                            <Check className="w-3.5 h-3.5" />
                            <span>Presente</span>
                          </button>

                          {/* Ausente */}
                          <button
                            type="button"
                            onClick={() => handleCambiarEstado(alumno.id_alumno, 'A')}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1 ${
                              estadoActual === 'A'
                                ? 'bg-rose-600 text-white shadow-xs'
                                : 'bg-white text-slate-600 border border-slate-200 hover:bg-rose-50 hover:text-rose-700'
                            }`}
                          >
                            <X className="w-3.5 h-3.5" />
                            <span>Ausente</span>
                          </button>

                          {/* Justificado */}
                          <button
                            type="button"
                            onClick={() => handleCambiarEstado(alumno.id_alumno, 'J')}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1 ${
                              estadoActual === 'J'
                                ? 'bg-amber-500 text-white shadow-xs'
                                : 'bg-white text-slate-600 border border-slate-200 hover:bg-amber-50 hover:text-amber-700'
                            }`}
                          >
                            <HelpCircle className="w-3.5 h-3.5" />
                            <span>Justificado</span>
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Pie de Acción: Botón Guardar Asistencia */}
            {alumnos.length > 0 && (
              <div className="p-4 sm:p-5 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 sticky bottom-0 z-10">
                <div className="text-xs text-slate-500 text-center sm:text-left">
                  <span>
                    Total a registrar: <strong>{alumnos.length} estudiantes</strong> (
                    {metricas.presentes} P, {metricas.ausentes} A, {metricas.justificados} J)
                  </span>
                </div>

                <button
                  type="button"
                  onClick={handleGuardarAsistencia}
                  disabled={guardando}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold px-6 py-3 rounded-xl transition shadow-md shadow-blue-500/20"
                >
                  {guardando ? (
                    <>
                      <Clock className="w-4 h-4 animate-spin" /> Guardando Asistencia...
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4" /> Guardar Asistencia del Grupo
                    </>
                  )}
                </button>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
