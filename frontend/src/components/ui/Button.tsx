/**
 * Button component – Tactical, high-contrast surveillance style.
 */
import { type ButtonHTMLAttributes, forwardRef } from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-xs font-semibold uppercase tracking-wider transition-all duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-accent)] disabled:pointer-events-none disabled:opacity-40 cursor-pointer select-none active:scale-[0.98]',
  {
    variants: {
      variant: {
        primary:
          'bg-[var(--color-accent)] text-[#04080e] hover:bg-[#26ecff] shadow-[0_0_15px_rgba(0,229,255,0.2)] border border-[#38f2ff]',
        secondary:
          'bg-[var(--color-surface-2)] text-[var(--color-text-primary)] border border-[var(--color-border-2)] hover:bg-[var(--color-surface-3)] hover:border-[var(--color-text-muted)]',
        ghost:
          'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-2)]',
        danger:
          'bg-[var(--color-danger)]/15 text-[var(--color-danger)] border border-[var(--color-danger)]/40 hover:bg-[var(--color-danger)]/25',
        outline:
          'border border-[var(--color-border-2)] text-[var(--color-text-primary)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent-subtle)]',
        subtle:
          'bg-[var(--color-surface)] text-[var(--color-text-secondary)] border border-[var(--color-border)] hover:text-[var(--color-text-primary)] hover:border-[var(--color-border-2)]',
      },
      size: {
        xs: 'h-7 px-2.5 text-[10px]',
        sm: 'h-8 px-3 text-[11px]',
        md: 'h-9 px-4 text-xs',
        lg: 'h-10 px-5 text-xs',
        icon: 'h-8 w-8 p-0',
        'icon-sm': 'h-7 w-7 p-0',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  },
)

Button.displayName = 'Button'

export { Button, buttonVariants }
