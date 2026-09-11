import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

export function NavBar() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link to="/dashboard" className="font-semibold text-slate-900">
          Adaptive Course Platform
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link to="/dashboard" className="text-slate-600 hover:text-slate-900">
            Courses
          </Link>
          <Link to="/analytics" className="text-slate-600 hover:text-slate-900">
            Analytics
          </Link>
          {user && <span className="text-slate-400">{user.email}</span>}
          <button
            onClick={handleLogout}
            className="rounded-md border border-slate-300 px-3 py-1 text-slate-700 hover:bg-slate-100"
          >
            Log out
          </button>
        </nav>
      </div>
    </header>
  )
}
