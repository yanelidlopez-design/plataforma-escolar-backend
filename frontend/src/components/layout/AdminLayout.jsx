import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Sidebar from './Sidebar';

/**
 * AdminLayout - Layout principal con navegación lateral.
 */
export default function AdminLayout() {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isSidebarHovered, setIsSidebarHovered] = useState(false);
  const sidebarExpanded = !isCollapsed || isSidebarHovered || isMobileOpen;

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar
        isCollapsed={!sidebarExpanded}
        setIsCollapsed={setIsCollapsed}
        isMobileOpen={isMobileOpen}
        setIsMobileOpen={setIsMobileOpen}
        onMouseEnter={() => setIsSidebarHovered(true)}
        onMouseLeave={() => setIsSidebarHovered(false)}
      />
      <div
        className={`min-h-screen transition-[margin] duration-300 ${
          sidebarExpanded ? 'md:ml-72' : 'md:ml-20'
        }`}
      >
        <button
          type="button"
          onClick={() => setIsMobileOpen(true)}
          className="fixed left-4 top-4 z-10 rounded-md bg-gray-900 p-2 text-white shadow md:hidden"
          aria-label="Abrir menú"
        >
          <Menu className="h-5 w-5" />
        </button>
        <main className="min-h-screen bg-gray-50 p-6 pt-16 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}