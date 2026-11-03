/**
 * Main application layout – tactical command shell with responsive layout.
 */
import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from '@/components/Sidebar'
import { Header } from '@/components/Header'

export function AppLayout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-[var(--color-background)] tactical-grid text-[var(--color-text-primary)]">
      {/* Sidebar with mobile drawer support */}
      <Sidebar
        mobileOpen={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)} 
      />

      {/* Main content container */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden bg-[var(--color-background)]/95 backdrop-blur-[1px]">
        <Header onToggleMobileMenu={() => setMobileMenuOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
