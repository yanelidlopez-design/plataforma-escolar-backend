import axiosInstance from './axiosInstance';

/**
 * asistencias.js - Servicios del módulo de Asistencia.
 * Endpoints bajo /api/academico/asistencias/
 */
export const getAsistencias = (params) => axiosInstance.get('/academico/asistencias/', { params });
export const getAsistencia = (id) => axiosInstance.get(`/academico/asistencias/${id}/`);
export const createAsistencia = (data) => axiosInstance.post('/academico/asistencias/', data);
export const updateAsistencia = (id, data) => axiosInstance.patch(`/academico/asistencias/${id}/`, data);
export const deleteAsistencia = (id) => axiosInstance.delete(`/academico/asistencias/${id}/`);
export const exportarAsistenciasCSV = (params) => axiosInstance.get('/academico/asistencias/exportar-csv/', { params, responseType: 'blob' });
export const exportarAsistenciasExcel = (params) => axiosInstance.get('/academico/asistencias/exportar-excel/', { params, responseType: 'blob' });
export const exportarAsistenciasPDF = (params) => axiosInstance.get('/academico/asistencias/exportar-pdf/', { params, responseType: 'blob' });
export const exportarEstadisticaMensualPDF = (params) => axiosInstance.get(
  '/academico/asistencias/estadistica-mensual-pdf/',
  { params, responseType: 'blob' },
);

/**
 * Servicios para estadísticas de plantel (asistencias) * Endpoint: GET /api/academico/asistencias/estadisticas-plantel/ */
export const obtenerEstadisticasPlantel = () => axiosInstance.get('/academico/asistencias/estadisticas-plantel/');
export const obtenerEstadisticasPlantelRango = (fechaInicio, fechaFin) => axiosInstance.get('/academico/asistencias/estadisticas-plantel/', { params: { fecha_inicio: fechaInicio, fecha_fin: fechaFin } });