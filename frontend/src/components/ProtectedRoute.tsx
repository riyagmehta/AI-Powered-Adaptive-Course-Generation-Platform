import type { ReactElement } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

interface ProtectedRouteProps {
  children: ReactElement
  requireOnboarding?: boolean
}

export function ProtectedRoute({ children, requireOnboarding = true }: ProtectedRouteProps) {
  const { token, user, isInitialized } = useAuthStore()

  if (!isInitialized) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-500">
        Loading&hellip;
      </div>
    )
  }

  if (!token || !user) {
    return <Navigate to="/login" replace />
  }

  if (requireOnboarding && !user.onboarding_completed) {
    return <Navigate to="/onboarding" replace />
  }

  return children
}
