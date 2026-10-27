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
  default: 'bg-line text-ink-muted',
  brand:   'bg-accent/20 text-accent-text border border-accent/30',
  blue:    'bg-secondary/20 text-secondary-text border border-secondary/30',
  amber:   'bg-warn/20 text-warn border border-warn/30',
  red:     'bg-bad/20 text-bad border border-bad/30',
  outline: 'border border-line text-ink-muted',
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
