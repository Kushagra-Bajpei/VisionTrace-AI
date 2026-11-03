/**
 * Axios API client – pre-configured for the VisionTrace AI backend.
 *
 * All requests go through this instance, which:
 * - Points to the correct base URL (proxied through Vite in dev).
 * - Attaches JSON content-type headers.
 * - Intercepts errors and normalises them.
 */
import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiError } from '@/types'

const API_BASE_URL = '/api/v1'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ── Request interceptor ───────────────────────────────────────────────────
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('visiontrace_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// ── Response interceptor ──────────────────────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      // If unauthorized on general request, purge stale token
      const isAuthRoute = error.config?.url?.includes('/auth/login') || error.config?.url?.includes('/auth/register')
      if (!isAuthRoute) {
        localStorage.removeItem('visiontrace_token')
        localStorage.removeItem('visiontrace_user')
      }
    }

    const detail =
      error.response?.data?.detail ??
      error.message ??
      'An unexpected error occurred'

    // Normalise error shape so consumers can rely on `error.message`
    const normalized = new Error(detail)
    ;(normalized as Error & { status?: number }).status =
      error.response?.status
    return Promise.reject(normalized)
  },
)

export default apiClient
