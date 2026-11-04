import axiosInstance from './axiosInstance';

/**
 * auth.js - Servicios de autenticación.
 */
export const login = (credentials) => axiosInstance.post('/core/token/', credentials);
export const logout = () => axiosInstance.post('/core/logout/');
export const getMe = () => axiosInstance.get('/core/usuarios/me/');
export const cambiarContrasena = (data) =>
  axiosInstance.post('/core/usuarios/cambiar-password/', data);
export const solicitarRestablecimiento = (email) =>
  axiosInstance.post('/core/password-reset/request/', { email });
export const confirmarRestablecimiento = (data) =>
  axiosInstance.post('/core/password-reset/confirm/', data);