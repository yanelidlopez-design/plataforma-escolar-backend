/**
 * Card - Componentes de tarjeta reutilizables (Card, CardHeader, CardTitle, CardContent).
 * Basados en el patrón shadcn/ui para Tailwind.
 */

export function Card({ children, className = '' }) {
  return (
    <div className={`rounded-xl border border-gray-200 bg-white shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ children, className = '' }) {
  return (
    <div className={`flex flex-col space-y-1.5 p-6 ${className}`}>
      {children}
    </div>
  );
}

export function CardTitle({ children, className = '' }) {
  return (
    <h3 className={`text-2xl font-semibold leading-none tracking-tight text-gray-900 ${className}`}>
      {children}
    </h3>
  );
}

export function CardContent({ children, className = '' }) {
  return (
    <div className={`p-6 pt-0 ${className}`}>{children}</div>
  );
}