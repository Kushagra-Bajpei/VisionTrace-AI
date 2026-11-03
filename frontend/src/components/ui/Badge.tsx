/**
 * Badge – Tactical status pill and telemetry tags.
 */
import { type HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-[4px] px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-medium transition-colors',
  {
    variants: {
      variant: {
        default:
          'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] border border-[var(--color-border-2)]',
        accent:
          'bg-[var(--color-accent-subtle)] text-[var(--color-accent)] border border-[var(--color-border-accent)]',
        completed:
          'bg-emerald-950/40 text-emerald-400 border border-emerald-500/30',
        uploaded:
          'bg-slate-900/60 text-slate-300 border border-slate-700/50',
        processing:
          'bg-sky-950/40 text-sky-400 border border-sky-500/30 animate-pulse',
        uploading:
          'bg-sky-950/40 text-sky-400 border border-sky-500/30 animate-pulse',
        queued:
          'bg-amber-950/40 text-amber-400 border border-amber-500/30',
        warning:
          'bg-amber-950/40 text-amber-400 border border-amber-500/30',
        success:
          'bg-emerald-950/40 text-emerald-400 border border-emerald-500/30',
        failed:
          'bg-rose-950/40 text-rose-400 border border-rose-500/30',
        danger:
          'bg-rose-950/40 text-rose-400 border border-rose-500/30',
        outline:
          'bg-transparent text-[var(--color-text-muted)] border border-[var(--color-border)]',
        telemetry:
          'bg-[#080d14] text-[var(--color-text-secondary)] border border-[#1b2636] font-mono text-[9px]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  dot?: boolean
}

export function Badge({ className, variant, dot, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props}>
      {dot && (
        <span
          className={cn(
            'w-1.5 h-1.5 rounded-full shrink-0',
            (variant === 'completed' || variant === 'success') && 'bg-emerald-400',
            variant === 'uploaded' && 'bg-slate-400',
            (variant === 'processing' || variant === 'uploading') && 'bg-sky-400 animate-ping',
            (variant === 'queued' || variant === 'warning') && 'bg-amber-400',
            (variant === 'failed' || variant === 'danger') && 'bg-rose-400',
            variant === 'accent' && 'bg-[var(--color-accent)]',
            (!variant || variant === 'default' || variant === 'outline') && 'bg-slate-400',
          )}
        />
      )}
      {children}
    </span>
  )
}
