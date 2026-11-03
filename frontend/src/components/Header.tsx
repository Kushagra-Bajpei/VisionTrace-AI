/**
 * Top header bar – Forensic telemetry breadcrumb, API health indicator, and mobile menu trigger.
 */
import { useLocation, Link } from 'react-router-dom'
import { Video as VideoIcon, HardDrive, Menu, LogOut } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useApiHealth } from '@/hooks/useApiHealth'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'

const routeLabels: Record<string, { label: string; code: string }> = {
  '/': { label: 'Operational Dashboard', code: 'MOD-01' },
  '/videos': { label: 'Video Footage Library', code: 'MOD-02' },
  '/search': { label: 'AI Semantic Search', code: 'MOD-03' },
  '/investigations': { label: 'Investigation Workspace', code: 'MOD-04' },
  '/reports': { label: 'Incident Reports & Evidence', code: 'MOD-05' },
  '/audit': { label: 'Security & Audit Logging', code: 'SEC-01' },
  '/settings': { label: 'System Configuration', code: 'SYS-00' },
}

interface HeaderProps {
  onToggleMobileMenu?: () => void
}

export function Header({ onToggleMobileMenu }: HeaderProps) {
  const location = useLocation()
  const { isConnected, health } = useApiHealth()
  const { user, logout, isAuthenticated } = useAuth()

  const currentModule =
    routeLabels[location.pathname] ?? {
      label: location.pathname.replace('/', '').replace(/-/g, ' ').toUpperCase(),
      code: 'APP-00',
    }

  const getRoleBadge = (role?: string) => {
    switch (role) {
      case 'admin':
        return 'bg-cyan-950/80 text-cyan-300 border-cyan-500/40'
      case 'investigator':
        return 'bg-blue-950/80 text-blue-300 border-blue-500/40'
      case 'reviewer':
        return 'bg-amber-950/80 text-amber-300 border-amber-500/40'
      default:
        return 'bg-slate-900 text-slate-300 border-slate-700'
    }
  }

  return (
    <header className="flex items-center justify-between h-14 px-4 sm:px-6 border-b border-[var(--color-border)] bg-[var(--color-surface)]/90 backdrop-blur-md shrink-0 z-20">
      {/* Mobile Menu Button & Breadcrumb */}
      <div className="flex items-center gap-3">
        {onToggleMobileMenu && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onToggleMobileMenu}
            className="lg:hidden text-[var(--color-text-secondary)] hover:text-white"
            aria-label="Open navigation menu"
          >
            <Menu className="w-4 h-4" />
          </Button>
        )}

        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-accent)] border border-[var(--color-border-accent)]">
          {currentModule.code}
        </span>
        <div className="h-3.5 w-px bg-[var(--color-border)] hidden sm:block" />
        <h1 className="text-xs sm:text-sm font-semibold tracking-wide text-[var(--color-text-primary)] uppercase font-mono truncate max-w-[180px] sm:max-w-none">
          {currentModule.label}
        </h1>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Quick Upload action if not already on /videos */}
        {location.pathname !== '/videos' && (
          <Button variant="secondary" size="xs" asChild>
            <Link to="/videos" className="flex items-center gap-1.5">
              <VideoIcon className="w-3.5 h-3.5 text-[var(--color-accent)]" />
              <span className="hidden sm:inline">Library</span>
            </Link>
          </Button>
        )}

        {/* Global Storage Status Indicator */}
        <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[11px] font-mono text-[var(--color-text-secondary)]">
          <HardDrive className="w-3 h-3 text-[var(--color-text-muted)]" />
          <span>Local SSD</span>
        </div>

        {/* API Telemetry Status */}
        <div className="flex items-center gap-2 px-2 py-1 rounded bg-[var(--color-surface-2)] border border-[var(--color-border)]">
          <span
            className={cn(
              'w-2 h-2 rounded-full shrink-0',
              isConnected
                ? 'bg-[var(--color-success)] shadow-[0_0_8px_rgba(16,185,129,0.6)]'
                : 'bg-[var(--color-danger)] animate-pulse',
            )}
          />
          <span className="text-[10px] sm:text-[11px] font-mono text-[var(--color-text-primary)]">
            {isConnected ? 'LIVE' : 'OFFLINE'}
          </span>
          {health?.version && (
            <span className="text-[10px] font-mono text-[var(--color-text-muted)] hidden xl:inline">
              v{health.version}
            </span>
          )}
        </div>

        {/* Authenticated Operator Profile & Logout */}
        {isAuthenticated && user && (
          <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
            <div className="flex items-center gap-1.5 font-mono">
              <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${getRoleBadge(user.role)}`}>
                {user.role}
              </span>
              <span className="hidden lg:inline text-xs text-slate-300 truncate max-w-[120px]">
                {user.full_name || user.email.split('@')[0]}
              </span>
            </div>
            <button
              onClick={() => logout()}
              title="Sign Out"
              className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-950/30 rounded transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
