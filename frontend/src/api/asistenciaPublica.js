import axiosInstance from './axiosInstance';

/**
 * asistenciaPublica.js - Servicios para gestión de enlaces de asistencia pública.
 * Endpoints bajo /api/core/asistencia-publica/
 *
 * Métodos:
 *   - listarEnlaces(): Listar todas las configuraciones de asistencia pública
 *   - crearEnlace(data): Crear una nueva configuración de asistencia
 *   - actualizarEnlace(id, data): Actualizar una configuración existente
 *   - eliminarEnlace(id): Eliminar una configuración
 *   - obtenerEnlacePorFecha(fecha): Obtener configuración activa para una fecha
 *   - obtenerEnlaceActivo(): Obtener la configuración activa del día
 */

// Listar todas las configuraciones de asistencia pública
export const listarEnlaceAsistencia = () => {
  return axiosInstance.get('/core/asistencia-publica/');
};

// Crear una nueva configuración de asistencia pública
export const crearEnlaceAsistencia = (data) => {
  return axiosInstance.post('/core/asistencia-publica/', data);
};

// Actualizar una configuración existente
export const actualizarEnlaceAsistencia = (id, data) => {
  return axiosInstance.put(`/core/asistencia-publica/${id}/`, data);
};

// Eliminar una configuración
export const eliminarEnlaceAsistencia = (id) => {
  return axiosInstance.delete(`/core/asistencia-publica/${id}/`);
};

// Obtener configuración activa para una fecha específica
export const obtenerEnlacePorFecha = (fecha) => {
  return axiosInstance.get(`/core/asistencia-publica/?fecha_dia=${fecha}`);
};

// Obtener la configuración activa del día
export const obtenerEnlaceActivo = () => {
  return axiosInstance.get('/core/asistencia/link/');
};