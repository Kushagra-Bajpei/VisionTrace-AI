/**
 * Sidebar navigation for VisionTrace AI.
 * Desktop fixed sidebar + Mobile slide-over drawer with backdrop.
 */
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Video,
  Search,
  FolderSearch,
  FileText,
  Settings,
  ShieldAlert,
  ShieldCheck,
  ChevronRight,
  Database,
  X,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { videoService } from '@/services/video'
import { cn } from '@/lib/utils'

interface NavItemDef {
  label: string
  href: string
  icon: React.ElementType
  badgeKey?: 'videos'
}

const navItems: NavItemDef[] = [
  { label: 'Dashboard', href: '/', icon: LayoutDashboard },
  { label: 'Video Library', href: '/videos', icon: Video, badgeKey: 'videos' },
  { label: 'AI Search', href: '/search', icon: Search },
  { label: 'Investigations', href: '/investigations', icon: FolderSearch },
  { label: 'Reports', href: '/reports', icon: FileText },
  { label: 'Audit Trail', href: '/audit', icon: ShieldCheck },
]

const bottomNavItems: NavItemDef[] = [
  { label: 'Settings', href: '/settings', icon: Settings },
]

interface SidebarProps {
  mobileOpen?: boolean
  onCloseMobile?: () => void
}

export function Sidebar({ mobileOpen = false, onCloseMobile }: SidebarProps) {
  const location = useLocation()

  const { data: stats } = useQuery({
    queryKey: ['video-stats'],
    queryFn: videoService.getVideoStats,
    staleTime: 30_000,
  })

  const sidebarContent = (
    <div className="flex flex-col h-full bg-[var(--color-surface)] border-r border-[var(--color-border)] select-none">
      {/* Brand Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)] bg-[var(--color-background)]/40">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border-accent)] shadow-[0_0_12px_rgba(0,229,255,0.15)]">
            <ShieldAlert className="w-4 h-4 text-[var(--color-accent)]" />
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-[var(--color-accent)] animate-pulse" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-bold tracking-tight text-[var(--color-text-primary)] font-mono">
                VISIONTRACE
              </span>
              <span className="px-1 py-0.2 text-[9px] font-bold font-mono text-[var(--color-accent)] bg-[var(--color-accent-subtle)] border border-[var(--color-border-accent)] rounded">
                AI
              </span>
            </div>
            <span className="text-[10px] text-[var(--color-text-muted)] font-mono tracking-wider uppercase">
              Forensic Intelligence
            </span>
          </div>
        </div>

        {/* Mobile close button */}
        {onCloseMobile && (
          <button
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 rounded text-[var(--color-text-muted)] hover:text-white"
            aria-label="Close navigation"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <p className="px-3 pb-2 text-[10px] font-mono uppercase tracking-widest text-[var(--color-text-muted)]">
          Investigation Modules
        </p>
        {navItems.map((item) => (
          <NavItemRow
            key={item.href}
            item={item}
            pathname={location.pathname}
            badgeCount={item.badgeKey === 'videos' ? stats?.total_videos : undefined}
            onClick={onCloseMobile}
          />
        ))}
      </nav>

      {/* Bottom Telemetry & Settings */}
      <div className="px-3 py-3 border-t border-[var(--color-border)] space-y-1 bg-[var(--color-background)]/20 shrink-0">
        {bottomNavItems.map((item) => (
          <NavItemRow
            key={item.href}
            item={item}
            pathname={location.pathname}
            onClick={onCloseMobile}
          />
        ))}

        <div className="px-2 pt-3 pb-1">
          <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] text-xs">
            <div className="flex items-center gap-2">
              <Database className="w-3.5 h-3.5 text-[var(--color-accent)]" />
              <div className="flex flex-col">
                <span className="text-[11px] font-mono text-[var(--color-text-primary)] font-medium">
                  Phase 3 Active
                </span>
                <span className="text-[9px] text-[var(--color-text-muted)] font-mono">
                  Storage & Ingestion
                </span>
              </div>
            </div>
            <div className="w-2 h-2 rounded-full bg-[var(--color-success)] shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
          </div>
        </div>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop Persistent Sidebar (w-64, hidden on mobile) */}
      <aside className="hidden lg:flex w-64 min-h-screen shrink-0">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer (visible only when mobileOpen is true) */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity"
            onClick={onCloseMobile}
            aria-hidden="true"
          />
          <div className="relative flex-1 flex flex-col max-w-xs w-full">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  )
}

function NavItemRow({
  item,
  pathname,
  badgeCount,
  onClick,
}: {
  item: NavItemDef
  pathname: string
  badgeCount?: number
  onClick?: () => void
}) {
  const isActive =
    item.href === '/'
      ? pathname === '/'
      : pathname.startsWith(item.href)

  return (
    <NavLink
      to={item.href}
      onClick={onClick}
      className={cn(
        'relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 group',
        isActive
          ? 'bg-[var(--color-surface-2)] text-[var(--color-accent)] font-semibold shadow-sm border border-[var(--color-border-accent)]'
          : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-2)]/60 border border-transparent',
      )}
    >
      {isActive && (
        <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r bg-[var(--color-accent)] shadow-[0_0_8px_rgba(0,229,255,0.6)]" />
      )}

      <item.icon
        className={cn(
          'w-4 h-4 shrink-0 transition-colors',
          isActive
            ? 'text-[var(--color-accent)]'
            : 'text-[var(--color-text-muted)] group-hover:text-[var(--color-text-primary)]',
        )}
      />
      <span className="flex-1 tracking-tight">{item.label}</span>

      {badgeCount !== undefined && badgeCount > 0 && (
        <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold rounded bg-[var(--color-surface-3)] text-[var(--color-text-secondary)] border border-[var(--color-border-2)]">
          {badgeCount}
        </span>
      )}

      {isActive && (
        <ChevronRight className="w-3.5 h-3.5 text-[var(--color-accent)] opacity-70" />
      )}
    </NavLink>
  )
}
