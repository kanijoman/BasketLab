/**
 * AuthContext — authentication stub.
 *
 * Today this always returns an "admin" mock user (local-only mode).
 * When auth is needed, replace the `AuthProvider` implementation with
 * a real JWT / session flow — all consumers stay unchanged.
 *
 * Role hierarchy: guest < free < premium < admin
 */
import { createContext, useContext, ReactNode } from 'react'

export type UserRole = 'guest' | 'free' | 'premium' | 'admin'

export interface User {
  id: string
  name: string
  email: string
  role: UserRole
}

interface AuthContextValue {
  user: User | null
  isAuthenticated: boolean
  hasRole: (required: UserRole) => boolean
  /** Stub — replace with real login when auth is added */
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const ROLE_ORDER: UserRole[] = ['guest', 'free', 'premium', 'admin']

const AuthContext = createContext<AuthContextValue | null>(null)

// ── Mock admin user for local development ────────────────────────────────────
const MOCK_USER: User = {
  id: 'local-admin',
  name: 'Admin Local',
  email: 'admin@local',
  role: 'admin',
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const hasRole = (required: UserRole): boolean => {
    if (!MOCK_USER) return required === 'guest'
    return ROLE_ORDER.indexOf(MOCK_USER.role) >= ROLE_ORDER.indexOf(required)
  }

  const login = async (_email: string, _password: string): Promise<void> => {
    // TODO: implement real auth — POST /api/v1/auth/login → JWT → httpOnly cookie
    console.warn('[AuthContext] login() stub called — no-op in local mode')
  }

  const logout = () => {
    // TODO: implement real logout — clear httpOnly cookie
    console.warn('[AuthContext] logout() stub called — no-op in local mode')
  }

  return (
    <AuthContext.Provider
      value={{
        user: MOCK_USER,
        isAuthenticated: true,
        hasRole,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
