import axios from 'axios'

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
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      if (window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }
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
