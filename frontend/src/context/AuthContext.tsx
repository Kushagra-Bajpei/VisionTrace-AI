/**
 * VisionTrace AI – Enterprise Authentication & Authorization Context.
 * Manages user credentials, JWT access token, RBAC capabilities, and scoped media delivery tokens.
 */
import React, { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { authService } from '@/services/auth'
import type { InvestigationCase, TokenResponse, User, UserRole } from '@/types'

interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  isAdmin: boolean
  isInvestigator: boolean
  isReviewer: boolean
  isViewer: boolean
  login: (email: string, password: string) => Promise<TokenResponse>
  register: (email: string, password: string, fullName?: string) => Promise<TokenResponse>
  bootstrapAdmin: (email: string, password: string, fullName?: string) => Promise<TokenResponse>
  logout: () => Promise<void>
  getMediaToken: (resourceType: 'video' | 'frame' | 'crop' | 'report', resourceId: string) => Promise<string>
  hasRole: (roles: UserRole[]) => boolean
  canCreateCase: boolean
  canEditCase: (caseItem?: InvestigationCase | null) => boolean
  canDeleteCase: (caseItem?: InvestigationCase | null) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const TOKEN_KEY = 'visiontrace_token'
const USER_KEY = 'visiontrace_user'

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem(USER_KEY)
    if (!saved) return null
    try {
      return JSON.parse(saved)
    } catch {
      return null
    }
  })
  const [isLoading, setIsLoading] = useState<boolean>(true)

  // Verify and hydrate current user on mount
  useEffect(() => {
    let mounted = true
    const initAuth = async () => {
      const storedToken = localStorage.getItem(TOKEN_KEY)
      if (storedToken) {
        try {
          const profile = await authService.getMe()
          if (mounted) {
            setUser(profile)
            localStorage.setItem(USER_KEY, JSON.stringify(profile))
          }
        } catch {
          if (mounted) {
            localStorage.removeItem(TOKEN_KEY)
            localStorage.removeItem(USER_KEY)
            setToken(null)
            setUser(null)
          }
        }
      }
      if (mounted) setIsLoading(false)
    }

    initAuth()
    return () => {
      mounted = false
    }
  }, [])

  const handleAuthSuccess = (res: TokenResponse): TokenResponse => {
    setToken(res.access_token)
    setUser(res.user)
    localStorage.setItem(TOKEN_KEY, res.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(res.user))
    return res
  }

  const login = async (email: string, password: string): Promise<TokenResponse> => {
    const res = await authService.login({ email, password })
    return handleAuthSuccess(res)
  }

  const register = async (email: string, password: string, fullName?: string): Promise<TokenResponse> => {
    const res = await authService.register({ email, password, full_name: fullName })
    return handleAuthSuccess(res)
  }

  const bootstrapAdmin = async (email: string, password: string, fullName?: string): Promise<TokenResponse> => {
    const res = await authService.bootstrapAdmin({ email, password, full_name: fullName })
    return handleAuthSuccess(res)
  }

  const logout = async (): Promise<void> => {
    try {
      await authService.logout()
    } catch {
      // Ignore network errors on logout
    } finally {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      setToken(null)
      setUser(null)
    }
  }

  const getMediaToken = async (
    resourceType: 'video' | 'frame' | 'crop' | 'report',
    resourceId: string
  ): Promise<string> => {
    return authService.getMediaToken(resourceType, resourceId)
  }

  const hasRole = (roles: UserRole[]): boolean => {
    if (!user) return false
    return roles.includes(user.role)
  }

  const isAdmin = user?.role === 'admin'
  const isInvestigator = user?.role === 'investigator'
  const isReviewer = user?.role === 'reviewer'
  const isViewer = user?.role === 'viewer'

  const canCreateCase = isAdmin || isInvestigator

  const canEditCase = (caseItem?: InvestigationCase | null): boolean => {
    if (!user || !caseItem) return false
    if (isAdmin) return true
    if (isInvestigator && (caseItem.owner_id === user.id || caseItem.lead_investigator_id === user.id)) {
      return true
    }
    return false
  }

  const canDeleteCase = (caseItem?: InvestigationCase | null): boolean => {
    if (!user || !caseItem) return false
    if (isAdmin) return true
    if (isInvestigator && caseItem.owner_id === user.id) return true
    return false
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        isAdmin,
        isInvestigator,
        isReviewer,
        isViewer,
        login,
        register,
        bootstrapAdmin,
        logout,
        getMediaToken,
        hasRole,
        canCreateCase,
        canEditCase,
        canDeleteCase,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
