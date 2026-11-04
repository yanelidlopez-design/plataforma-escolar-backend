import axios from 'axios';

/**
 * axiosInstance - Instancia configurada de axios para consumir la API Django.
 * Incluye el token JWT en cada petición si existe en localStorage.
 */
const axiosInstance = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

let refreshRequest = null;

// Interceptor para inyectar el token JWT en cada petición
axiosInstance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor para manejar errores de autenticación (401)
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const request = error.config;
    if (error.response?.status === 401 && request && !request._retry) {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        request._retry = true;
        try {
          if (!refreshRequest) {
            refreshRequest = axios.post('/api/token/refresh/', { refresh: refreshToken })
              .then((response) => {
                localStorage.setItem('access_token', response.data.access);
                return response.data.access;
              })
              .finally(() => {
                refreshRequest = null;
              });
          }
          const accessToken = await refreshRequest;
          request.headers = request.headers || {};
          request.headers.Authorization = `Bearer ${accessToken}`;
          return axiosInstance(request);
        } catch (refreshError) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
          return Promise.reject(refreshError);
        }
      }

      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default axiosInstance;