import { create } from 'zustand'
import { TOKEN_STORAGE_KEY, api } from '../lib/api'
import type { OnboardingUpdate, Token, UserRead } from '../types/api'

interface AuthState {
  token: string | null
  user: UserRead | null
  isLoading: boolean
  isInitialized: boolean
  error: string | null
  register: (email: string, password: string, fullName: string) => Promise<void>
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
  completeOnboarding: (payload: OnboardingUpdate) => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem(TOKEN_STORAGE_KEY),
  user: null,
  isLoading: false,
  isInitialized: false,
  error: null,

  register: async (email, password, fullName) => {
    set({ isLoading: true, error: null })
    try {
      await api.post<UserRead>('/auth/register', { email, password, full_name: fullName })
      await get().login(email, password)
    } catch (err) {
      set({ error: extractErrorMessage(err), isLoading: false })
      throw err
    }
  },

  login: async (email, password) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.post<Token>('/auth/login', { email, password })
      localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
      set({ token: data.access_token })
      await get().fetchMe()
    } catch (err) {
      set({ error: extractErrorMessage(err), isLoading: false })
      throw err
    } finally {
      set({ isLoading: false })
    }
  },

  logout: () => {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    set({ token: null, user: null })
  },

  fetchMe: async () => {
    try {
      const { data } = await api.get<UserRead>('/auth/me')
      set({ user: data, isInitialized: true })
    } catch {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      set({ token: null, user: null, isInitialized: true })
    }
  },

  completeOnboarding: async (payload) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.patch<UserRead>('/auth/onboarding', payload)
      set({ user: data })
    } catch (err) {
      set({ error: extractErrorMessage(err) })
      throw err
    } finally {
      set({ isLoading: false })
    }
  },

  clearError: () => set({ error: null }),
}))

export function extractErrorMessage(err: unknown): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const response = (err as { response?: { data?: { detail?: unknown } } }).response
    const detail = response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((d) => (typeof d === 'object' && d && 'msg' in d ? String(d.msg) : String(d))).join(', ')
    }
  }
  if (err instanceof Error) return err.message
  return 'Something went wrong. Please try again.'
}
