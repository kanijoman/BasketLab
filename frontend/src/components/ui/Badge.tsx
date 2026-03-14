/**
 * Badge — small status/label pill.
 *
 * Variants: default | brand | blue | amber | red | outline
 */
import { cn } from '@/lib/utils'
import { ReactNode } from 'react'

type Variant = 'default' | 'brand' | 'blue' | 'amber' | 'red' | 'outline'

interface Props {
  children: ReactNode
  variant?: Variant
  className?: string
}

const VARIANTS: Record<Variant, string> = {
  default: 'bg-surface-border text-ink-secondary',
  brand:   'bg-brand-600/20 text-brand-400 border border-brand-600/30',
  blue:    'bg-accent-600/20 text-accent-400 border border-accent-600/30',
  amber:   'bg-warn/20 text-warn border border-warn/30',
  red:     'bg-down/20 text-down border border-down/30',
  outline: 'border border-surface-border text-ink-secondary',
}

export default function Badge({ children, variant = 'default', className }: Props) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-pill text-xs font-medium',
        VARIANTS[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}
