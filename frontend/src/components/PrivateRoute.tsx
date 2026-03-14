/**
 * PrivateRoute — role-based access guard.
 *
 * Today the mock user is always "admin", so all routes pass.
 * When real auth is implemented, replace AuthContext — this component stays.
 *
 * Usage:
 *   <PrivateRoute requiredRole="premium">
 *     <AIAnalysisPage />
 *   </PrivateRoute>
 */
import { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth, UserRole } from '@/context/AuthContext'
import { Lock } from 'lucide-react'

interface Props {
  requiredRole?: UserRole
  children: ReactNode
  /** If true, renders a "locked" overlay instead of redirecting */
  showLocked?: boolean
}

export default function PrivateRoute({
  requiredRole = 'free',
  children,
  showLocked = false,
}: Props) {
  const { isAuthenticated, hasRole } = useAuth()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/" state={{ from: location }} replace />
  }

  if (!hasRole(requiredRole)) {
    if (showLocked) {
      return (
        <div className="flex flex-col items-center justify-center h-64 gap-3 text-ink-secondary">
          <Lock className="w-10 h-10 opacity-40" />
          <p className="text-sm">Esta funcionalidad requiere un plan superior.</p>
        </div>
      )
    }
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
