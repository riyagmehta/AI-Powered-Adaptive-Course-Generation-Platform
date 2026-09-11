import axios from 'axios'
import { toast } from '../store/toastStore'

export const TOKEN_STORAGE_KEY = 'course_platform_token'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status

    if (status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      if (window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    } else if (status === 429) {
      toast.error("You're doing that a bit fast — please wait a moment and try again.")
    } else if (!error.response) {
      toast.error('Network error — check your connection and try again.')
    } else if (status >= 500) {
      toast.error('Something went wrong on our end. Please try again shortly.')
    }
    // Expected 4xx validation errors (bad login, invalid input, etc.) are
    // left for the calling page to show inline, rather than double-toasting.

    return Promise.reject(error)
  },
)

export function apiUrl(path: string): string {
  return `${import.meta.env.VITE_API_URL}${path}`
}

export function authHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}
