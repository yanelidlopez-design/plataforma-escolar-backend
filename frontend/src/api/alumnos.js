import axiosInstance from './axiosInstance';

/**
 * alumnos.js - Servicios del módulo de Alumnos.
 * Endpoints bajo /api/academico/alumnos/
 */
export const getAlumnos = (params) => axiosInstance.get('/academico/alumnos/', { params });
export const getAlumno = (id) => axiosInstance.get(`/academico/alumnos/${id}/`);
export const createAlumno = (data) => axiosInstance.post('/academico/alumnos/', data);
export const updateAlumno = (id, data) => axiosInstance.put(`/academico/alumnos/${id}/`, data);
export const deleteAlumno = (id) => axiosInstance.delete(`/academico/alumnos/${id}/`);
export const exportarAlumnos = (formato, params) =>
  axiosInstance.get(`/academico/alumnos/exportar-alumnos-${formato}/`, {
    params,
    responseType: 'blob',
  });