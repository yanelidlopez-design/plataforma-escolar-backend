import axiosInstance from './axiosInstance';

/**
 * urls.js - Servicios para gestión de URLs externas (inscripciones).
 * Endpoints bajo /api/academico/periodos/
 */
export const getPeriodosInscripcion = () => axiosInstance.get('/academico/periodos/');
export const alternarEstadoPeriodo = (id) => axiosInstance.patch(`/academico/periodos/${id}/alternar-estado/`);