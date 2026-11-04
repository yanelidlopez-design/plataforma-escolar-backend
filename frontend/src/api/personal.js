import axiosInstance from './axiosInstance';

/**
 * personal.js - Servicios del módulo de Personal/Profesores.
 * Endpoints bajo /api/personal/personal/
 */
export const getPersonal = (params) => axiosInstance.get('/personal/personal/', { params });
export const getPersona = (id) => axiosInstance.get(`/personal/personal/${id}/`);
export const createPersona = (data) => axiosInstance.post('/personal/personal/', data);
export const updatePersona = (id, data) => axiosInstance.put(`/personal/personal/${id}/`, data);
export const deletePersona = (id) => axiosInstance.delete(`/personal/personal/${id}/`);
export const restablecerContrasenaPersonal = (id, data) =>
  axiosInstance.post(`/personal/personal/${id}/restablecer-password/`, data);
export const exportarPersonal = (formato, params) =>
  axiosInstance.get(`/personal/personal/exportar-${formato}/`, {
    params,
    responseType: 'blob',
  });