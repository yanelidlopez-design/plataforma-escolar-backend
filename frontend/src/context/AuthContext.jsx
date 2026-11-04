import { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import axiosInstance from '../api/axiosInstance';

const AuthContext = createContext(null);

/**
 * AuthContext - Gestiona el estado de autenticación JWT del usuario.
 * Proporciona: user, token, isAuthenticated, login, logout, loading.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('access_token') || null);
  const [loading, setLoading] = useState(true);

  // Verificar si el token es válido al montar
  useEffect(() => {
    const verifyToken = async () => {
      try {
        if (token) {
          const response = await axiosInstance.get('/core/usuarios/me/', {
            headers: { Authorization: `Bearer ${token}` },
          });
          setUser(response.data);
        }
      } catch (error) {
        // Token inválido o expirado
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    verifyToken();
  }, [token]);

  const login = async ({ nombre_usuario, password }) => {
    const response = await axios.post('/api/core/token/', {
      username: nombre_usuario,
      password,
    });
    const { access, refresh } = response.data;
    localStorage.setItem('access_token', access);
    if (refresh) {
      localStorage.setItem('refresh_token', refresh);
    } else {
      localStorage.removeItem('refresh_token');
    }
    setToken(access);
    setUser(response.data.user || null);
    return response.data;
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  };

  const value = {
    user,
    token,
    isAuthenticated: !!token,
    login,
    logout,
    loading,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de un AuthProvider');
  }
  return context;
};