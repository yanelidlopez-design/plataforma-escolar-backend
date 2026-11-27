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

/** Exportar constancias en lote (Word .docx) */
export const exportarConstanciasLoteDOCX = ({ grado, seccion, periodo }) =>
  axiosInstance.get('/academico/prosecucion/exportar-lote/', {
    params: { grado, seccion, periodo },
    responseType: 'blob',
  });

/** Alias retrocompatible para exportación en lote */
export const exportarConstanciasLoteXLSX = exportarConstanciasLoteDOCX;

/** Descargar constancia individual en Word (.docx) */
export const descargarConstanciaProcesionDOCX = (alumnoId) =>
  axiosInstance.get(`/academico/prosecucion/alumno/${alumnoId}/exportar/`, {
    responseType: 'blob',
  });

/** Alias retrocompatible para descarga individual */
export const descargarConstanciaProcesionXLSX = descargarConstanciaProcesionDOCX;