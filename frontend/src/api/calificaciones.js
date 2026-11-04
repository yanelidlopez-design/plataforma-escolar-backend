import axiosInstance from './axiosInstance';

/**
 * calificaciones.js - Servicios del módulo de Calificaciones.
 * Endpoints bajo /api/academico/calificaciones/ y /api/academico/periodos-calificacion/
 */
export const getPeriodosCalificacion = (params) => axiosInstance.get('/academico/periodos-calificacion/', { params });
export const getCalificaciones = (params) => axiosInstance.get('/academico/calificaciones/', { params });
export const getCalificacion = (id) => axiosInstance.get(`/academico/calificaciones/${id}/`);
export const createCalificacion = (data) => axiosInstance.post('/academico/calificaciones/', data);
export const updateCalificacion = (id, data) => axiosInstance.patch(`/academico/calificaciones/${id}/`, data);
export const deleteCalificacion = (id) => axiosInstance.delete(`/academico/calificaciones/${id}/`);
/**
 * Carga masiva de criterios cualitativos por sección (lápso).
 * Endpoint: /api/academico/calificaciones/cargar-criterios-externa/
 */
export const cargarCriteriosExternos = (data) => axiosInstance.post('/academico/calificaciones/cargar-criterios-externa/', data);
/**
 * Carga de calificaciones numéricas externas.
 * Endpoint: /api/academico/calificaciones/cargar-externa/
 */
export const cargarCalificacionesExternas = (data) => axiosInstance.post('/academico/calificaciones/cargar-externa/', data);
export const getEvaluacionesCualitativas = (params) =>
  axiosInstance.get('/academico/evaluaciones-cualitativas/', { params });
export const guardarEvaluacionesCualitativas = (data) =>
  axiosInstance.post('/academico/evaluaciones-cualitativas/', data);
export const crearCriterioCualitativo = (data) =>
  axiosInstance.post('/academico/criterios-cualitativos/', data);
export const retirarCriterioCualitativo = (params) =>
  axiosInstance.delete('/academico/criterios-cualitativos/', { params });
export const exportarBoletaCualitativa = (formato, alumnoId, periodoId) =>
  axiosInstance.get(
    `/academico/calificaciones/boleta-cualitativa-${formato}/${alumnoId}/${periodoId}/`,
    { responseType: 'blob' },
  );