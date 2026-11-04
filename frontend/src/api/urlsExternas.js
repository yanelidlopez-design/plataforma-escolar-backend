import axiosInstance from './axiosInstance';

/**
 * urlsExternas.js - Servicios para gestión de URLs externas dinámicas.
 * Usa los endpoints de periodos de inscripción del backend:
 *   GET    /api/academico/periodos/           -> listar URLs externas
 *   PATCH  /api/academico/periodos/<id>/      -> editar slug, fechas, estado
 *   PATCH  /api/academico/periodos/<id>/alternar-estado/ -> switch Activo/Inactivo
 */
export const getUrlsExternas = (params) => axiosInstance.get('/academico/periodos/', { params });
export const getUrlExterna = (id) => axiosInstance.get(`/academico/periodos/${id}/`);
export const createUrlExterna = (data) => axiosInstance.post('/academico/periodos/', data);
export const updateUrlExterna = (id, data) => axiosInstance.patch(`/academico/periodos/${id}/`, data);
export const alternarEstadoUrlExterna = (id, activo_manual) =>
  axiosInstance.patch(`/academico/periodos/${id}/alternar-estado/`, { activo_manual });
export const deleteUrlExterna = (id) => axiosInstance.delete(`/academico/periodos/${id}/`);
export const getUrlExternaPublica = (token) =>
  axiosInstance.get(`/academico/periodos/publicos/${token}/`);