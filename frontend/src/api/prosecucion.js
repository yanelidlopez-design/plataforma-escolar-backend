import axiosInstance from './axiosInstance';

/**
 * prosecucion.js - Servicios para Constancia de Procesión en Educación Primaria.
 * Endpoints bajo /api/academico/prosecucion/
 */

/** Configuración institucional (singleton: pk=1) */
export const getConfiguracionInstitucional = () =>
  axiosInstance.get('/academico/prosecucion/configuracion/');

export const guardarConfiguracionInstitucional = (data) =>
  axiosInstance.post('/academico/prosecucion/configuracion/', data);

export const actualizarConfiguracionInstitucional = (data) =>
  axiosInstance.put('/academico/prosecucion/configuracion/', data);

/** Datos de prosecución por alumno */
export const getConstanciaProsecucionAlumno = (alumnoId, periodoEscolar) =>
  axiosInstance.get(`/academico/prosecucion/alumno/${alumnoId}/`, {
    params: { periodo_escolar: periodoEscolar },
  });

export const guardarConstanciaProsecucionAlumno = (alumnoId, data) =>
  axiosInstance.post(`/academico/prosecucion/alumno/${alumnoId}/`, data);

/** Exportar constancias en lote (PDF multipágina) */
export const exportarConstanciasLotePDF = ({ grado, seccion, periodo }) =>
  axiosInstance.get('/academico/prosecucion/exportar-lote/', {
    params: { grado, seccion, periodo },
    responseType: 'blob',
  });

/** Descargar constancia individual en PDF */
export const descargarConstanciaProcesionPDF = (alumnoId) =>
  axiosInstance.get(`/academico/calificaciones/prosecucion-final-pdf/${alumnoId}/`, {
    responseType: 'blob',
  });