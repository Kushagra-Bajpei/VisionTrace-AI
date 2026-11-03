/**
 * Loading states, high-precision progress bars, and empty states.
 */
import { cn } from '@/lib/utils'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function Spinner({ size = 'md', className }: SpinnerProps) {
  const sizes = {
    sm: 'h-3.5 w-3.5 border-2',
    md: 'h-5 w-5 border-2',
    lg: 'h-8 w-8 border-[3px]',
  }

  return (
    <div
      className={cn(
        'animate-spin rounded-full border-[var(--color-border-2)] border-t-[var(--color-accent)]',
        sizes[size],
        className,
      )}
      role="status"
      aria-label="Loading"
    />
  )
}

interface ProgressBarProps {
  percent: number
  label?: string
  sublabel?: string
  className?: string
  color?: 'accent' | 'success' | 'warning' | 'danger'
}

export function ProgressBar({
  percent,
  label,
  sublabel,
  className,
  color = 'accent',
}: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, percent))

  const fillColors = {
    accent: 'bg-[var(--color-accent)] shadow-[0_0_12px_rgba(0,229,255,0.4)]',
    success: 'bg-[var(--color-success)]',
    warning: 'bg-[var(--color-warning)]',
    danger: 'bg-[var(--color-danger)]',
  }

  return (
    <div className={cn('w-full space-y-1.5', className)}>
      {(label || sublabel) && (
        <div className="flex items-center justify-between text-xs font-mono">
          {label && <span className="text-[var(--color-text-secondary)]">{label}</span>}
          {sublabel && (
            <span className="text-[var(--color-accent)] font-semibold">{sublabel}</span>
          )}
        </div>
      )}
      <div className="h-1.5 w-full bg-[var(--color-surface-3)] rounded-full overflow-hidden border border-[var(--color-border)]">
        <div
          className={cn('h-full transition-all duration-200 ease-out', fillColors[color])}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}

interface SkeletonProps {
  className?: string
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded bg-[var(--color-surface-2)] border border-[var(--color-border)]/50',
        className,
      )}
    />
  )
}

interface LoadingStateProps {
  message?: string
  className?: string
}

export function LoadingState({
  message = 'Processing surveillance data…',
  className,
}: LoadingStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-16 text-[var(--color-text-secondary)]',
        className,
      )}
    >
      <Spinner size="lg" />
      <p className="text-xs font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
        {message}
      </p>
    </div>
  )
}

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-4 py-16 px-6 text-center rounded-xl border border-dashed border-[var(--color-border-2)] bg-[var(--color-surface)]/50',
        className,
      )}
    >
      {icon && (
        <div className="p-3.5 rounded-xl bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-accent)] shadow-sm">
          {icon}
        </div>
      )}
      <div className="space-y-1.5 max-w-sm">
        <h4 className="text-sm font-semibold font-mono tracking-wide uppercase text-[var(--color-text-primary)]">
          {title}
        </h4>
        {description && (
          <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
