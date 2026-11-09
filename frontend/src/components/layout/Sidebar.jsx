import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Users,
  User,
  Clock,
  FileText,
  Settings,
  BarChart3,
  LogOut,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  KeyRound,
} from 'lucide-react';
import PasswordChangeModal from '../common/PasswordChangeModal';

/**
 * Sidebar - Barra lateral colapsable con diseño oscuro (estilo referencia).
 * Fondo azul marino oscuro, ítems con íconos blancos y texto blanco.
 */
export default function Sidebar({
  isCollapsed,
  setIsCollapsed,
  isMobileOpen,
  setIsMobileOpen,
  onMouseEnter,
  onMouseLeave,
}) {
  const location = useLocation();
  const { logout } = useAuth();
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);

  const menuItems = [
    { path: '/admin/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/admin/dashboard/alumnos', icon: Users, label: 'Alumnos' },
    { path: '/admin/dashboard/personal', icon: User, label: 'Personal' },
    { path: '/admin/dashboard/asistencia', icon: Clock, label: 'Asistencia' },
    { path: '/admin/dashboard/calificaciones', icon: FileText, label: 'Calificaciones' },
    { path: '/admin/dashboard/configuracion-urls', icon: ShieldAlert, label: 'Config. Enlaces' },
    { path: '/admin/dashboard/configuracion-enlace', icon: Link, label: 'Conf. Enlace' },
    { path: '/admin/dashboard/reportes', icon: BarChart3, label: 'Reportes' },
  ];

  return (
    <>
      {/* Overlay móvil */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      <aside
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        className={`fixed inset-y-0 left-0 z-30 flex h-screen flex-col border-r border-gray-800 bg-gray-900 text-white shadow-sidebar transition-all duration-300 ease-in-out ${
          isCollapsed ? 'w-20' : 'w-72'
        } ${isMobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        {/* Header del sidebar con logo */}
        <div className="flex items-center h-16 px-3 bg-gray-900 border-b border-gray-800">
          <button
            type="button"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="hidden p-2 rounded-md hover:bg-gray-800 transition-colors md:block"
            aria-label={isCollapsed ? 'Expandir menú' : 'Contraer menú'}
          >
            {isCollapsed ? (
              <ChevronRight className="w-5 h-5" />
            ) : (
              <ChevronLeft className="w-5 h-5" />
            )}
          </button>
          <button
            type="button"
            onClick={() => setIsMobileOpen(false)}
            className="p-2 rounded-md hover:bg-gray-800 transition-colors md:hidden"
            aria-label="Cerrar menú"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          {!isCollapsed && (
            <div className="ml-3 flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">PE</span>
                </div>
                <div className="min-w-0">
                  <h1 className="text-sm font-bold text-white leading-tight">Plataforma Escolar</h1>
                  <p className="text-[10px] text-gray-400 leading-tight">Panel Administrativo</p>
                </div>
              </div>
            </div>
          )}
        </div>

        <nav className="flex-1 py-4 overflow-y-auto">
          <div className="px-3 space-y-1">
            {menuItems.map((item) => {
              const isActive = location.pathname === item.path;
              const Icon = item.icon;
              return (
                <Link
                  key={item.label}
                  to={item.path}
                  onClick={() => setIsMobileOpen(false)}
                  className={`flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors ${
                    isActive
                      ? 'bg-primary-600/20 text-primary-300 border-r-2 border-primary-600'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                  }`}
                >
                  <Icon className={`w-5 h-5 ${isCollapsed ? 'mx-auto mb-1' : 'mr-3 shrink-0'}`} />
                  {!isCollapsed && <span className="whitespace-nowrap">{item.label}</span>}
                </Link>
              );
            })}
          </div>
        </nav>

        <div className="p-3 border-t border-gray-800">
          <button
            type="button"
            onClick={() => {
              setIsMobileOpen(false);
              setPasswordModalOpen(true);
            }}
            className="mb-1 w-full flex items-center px-3 py-2.5 text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
            title={isCollapsed ? 'Cambiar contraseña' : undefined}
          >
            <KeyRound className="w-4 h-4 mr-3 shrink-0" />
            {!isCollapsed && <span className="whitespace-nowrap">Cambiar contraseña</span>}
          </button>
          <button
            type="button"
            onClick={logout}
            className="w-full flex items-center px-3 py-2.5 text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4 mr-3 shrink-0" />
            {!isCollapsed && <span className="whitespace-nowrap">Cerrar sesión</span>}
          </button>
        </div>
      </aside>
      <PasswordChangeModal
        isOpen={passwordModalOpen}
        onClose={() => setPasswordModalOpen(false)}
      />
    </>
  );
}