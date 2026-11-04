import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Users, Clock, BookOpen, GraduationCap } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/common/Card';
import axiosInstance from '../api/axiosInstance';

/**
 * Dashboard - Página principal con tarjetas de estadísticas (estilo referencia).
 * Ruta: /admin/dashboard
 */
const StatCard = ({ title, value, icon: Icon, color, subtitle }) => (
  <Card className="p-5">
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
      <div>
        <CardTitle className="text-xs font-medium text-gray-500 uppercase tracking-wider">
          {title}
        </CardTitle>
      </div>
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}-100 ${color}-600`}>
        <Icon className="w-5 h-5" />
      </div>
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      {subtitle && <div className="text-xs text-gray-500 mt-1">{subtitle}</div>}
    </CardContent>
  </Card>
);

export default function Dashboard() {
  const navigate = useNavigate();
  const [dashboardStats, setDashboardStats] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    axiosInstance.get('/academico/dashboard/estadisticas/')
      .then(({ data }) => {
        if (active) setDashboardStats(data);
      })
      .catch((requestError) => {
        console.error('Error al cargar estadísticas del dashboard:', requestError);
        if (active) {
          setError('No se pudieron cargar las estadísticas del plantel.');
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const statCards = [
    {
      title: 'Alumnos registrados',
      value: dashboardStats?.alumnos_registrados ?? '—',
      icon: Users,
      color: 'bg-purple',
      subtitle: 'Registros de alumnos en el sistema',
    },
    {
      title: 'Personal registrado',
      value: dashboardStats?.personal_registrado ?? '—',
      icon: GraduationCap,
      color: 'bg-green',
      subtitle: 'Docentes y personal administrativo',
    },
    {
      title: 'Asistencias Hoy',
      value: dashboardStats?.asistencias_hoy ?? '—',
      icon: Clock,
      color: 'bg-blue',
      subtitle: 'Registros de asistencia del día',
    },
    {
      title: 'Inscripciones activas',
      value: dashboardStats?.inscripciones_activas ?? '—',
      icon: BookOpen,
      color: 'bg-yellow',
      subtitle: 'Alumnos con inscripción vigente',
    },
  ];

  const quickActions = [
    {
      label: 'Nuevo Alumno',
      icon: <Plus className="w-4 h-4" />,
      color: 'bg-primary-600',
      textColor: 'text-white',
      onClick: () => navigate('/admin/dashboard/alumnos?accion=nuevo'),
    },
    {
      label: 'Ver Personal',
      icon: <Users className="w-4 h-4" />,
      color: 'bg-gray-200',
      textColor: 'text-gray-700',
      onClick: () => navigate('/admin/dashboard/personal'),
    },
    {
      label: 'Registrar Asistencia',
      icon: <Clock className="w-4 h-4" />,
      color: 'bg-gray-200',
      textColor: 'text-gray-700',
      onClick: () => navigate('/admin/dashboard/asistencia'),
    },
    {
      label: 'Cargar Calificaciones',
      icon: <BookOpen className="w-4 h-4" />,
      color: 'bg-gray-200',
      textColor: 'text-gray-700',
      onClick: () => navigate('/admin/dashboard/calificaciones'),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500">
          Resumen general del plantel educativo.
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat, i) => (
          <StatCard key={i} {...stat} />
        ))}
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Acciones rápidas</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          {quickActions.map((action, i) => (
            <button
              key={i}
              onClick={action.onClick}
              className={`flex flex-col items-center gap-2 p-3 rounded-xl border border-gray-200 ${action.color} ${action.textColor} text-xs font-medium hover:opacity-90 transition-colors`}
            >
              {action.icon}
              <span>{action.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}