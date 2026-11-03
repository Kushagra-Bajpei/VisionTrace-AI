/**
 * VisionTrace AI – Root Application
 * Configures TanStack Query, AuthProvider, and Protected React Router tree.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import { AppLayout } from '@/layouts/AppLayout'
import { DashboardPage } from '@/pages/Dashboard'
import { VideoLibraryPage } from '@/pages/VideoLibrary'
import { AISearchPage } from '@/pages/AISearch'
import { InvestigationsPage } from '@/pages/Investigations'
import { CaseWorkspacePage } from '@/pages/CaseWorkspace'
import { AuditLogPage } from '@/pages/AuditLogPage'
import { Login } from '@/pages/Login'
import { ReportsPage } from '@/pages/ReportsPage'
import {
  SettingsPage,
} from '@/pages/Placeholders'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
})

function AppRoutes() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#07090e] flex flex-col items-center justify-center gap-3">
        <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
        <span className="text-xs font-mono uppercase tracking-widest text-slate-400">
          Authenticating Surveillance Session...
        </span>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Login />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="videos" element={<VideoLibraryPage />} />
          <Route path="search" element={<AISearchPage />} />
          <Route path="investigations" element={<InvestigationsPage />} />
          <Route path="investigations/:caseId" element={<CaseWorkspacePage />} />
          <Route path="cases/:caseId" element={<CaseWorkspacePage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="audit" element={<AuditLogPage />} />
          <Route path="settings" element={<SettingsPage />} />
          {/* Catch-all → Dashboard */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </QueryClientProvider>
  )
}
