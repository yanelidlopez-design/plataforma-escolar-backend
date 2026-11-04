import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, Clock, FileText, LogOut, Star, User as UserIcon } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

/**
 * Header - Barra superior oscura azul con navegación por pestañas (estilo referencia).
 */
export default function Header({ onToggleSidebar }) {
  const { user, logout } = useAuth();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const navItems = [
    { path: '/admin/dashboard/personal', label: 'Personal', icon: UserIcon },
    { path: '/admin/dashboard/alumnos', label: 'Alumnos', icon: UserIcon },
    { path: '/admin/dashboard/inscripciones', label: 'Inscripciones', icon: FileText },
    { path: '/admin/dashboard/asistencia', label: 'Asistencias', icon: Clock },
    { path: '/admin/dashboard/calificaciones', label: 'Calificaciones', icon: Star },
  ];

  const rolLabel = {
    admin: 'Administrador',
    profesor: 'Profesor',
    directivo: 'Directivo',
    secretaria: 'Secretaria',
    alumno: 'Alumno',
  };

  return (
    <header className="fixed top-0 left-0 right-0 h-16 bg-slate-900 border-b border-slate-700 z-20 flex items-center justify-between px-4">
      {/* Izquierda: logo + toggle sidebar */}
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleSidebar}
          className="p-2 text-slate-400 hover:text-white md:hidden"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
        </button>
        <div className="flex items-center gap-1">
          <div className="w-6 h-6 bg-blue-600 rounded flex items-center justify-center text-xs font-bold">
            P
          </div>
          <span className="text-sm font-bold text-white hidden sm:block">Sistema de Gestión</span>
        </div>
      </div>

      {/* Centro: navegación por pestañas */}
      <div className="hidden md:flex items-center gap-1 px-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = true; // Simplificado; se podría usar useLocation
          return (
            <Link
              key={item.label}
              to={item.path}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>

      {/* Derecha: notificaciones, cerrar sesión, perfil */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setNotificationsOpen(!notificationsOpen)}
          className="relative p-2 text-slate-400 hover:text-white"
        >
          <Bell className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
        </button>

        <button
          onClick={logout}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-red-400 hover:bg-red-500/10 hover:text-red-300 rounded-lg transition-colors border border-transparent hover:border-red-500/30"
        >
          <LogOut className="w-4 h-4" />
          <span>Cerrar Sesión</span>
        </button>

        <div className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2 p-2 text-slate-400 hover:text-white focus:outline-none"
          >
            <div className="w-7 h-7 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold">
              {user?.nombre_usuario?.charAt(0) || 'U'}
            </div>
          </button>
          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-slate-800 border border-slate-700 rounded-lg shadow-lg py-2 z-30">
              <div className="px-4 py-2 border-b border-slate-700">
                <p className="text-sm font-medium text-white">{user?.nombre_usuario}</p>
                <p className="text-xs text-slate-400 capitalize">{rolLabel[user.rol] || user.rol}</p>
              </div>
              <button
                onClick={logout}
                className="w-full px-4 py-2 text-left text-sm text-red-400 hover:bg-red-500/10 hover:text-red-300 rounded-lg transition-colors"
              >
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}