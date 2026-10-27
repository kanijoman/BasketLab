/** Badge — a small label (issue #190: the tones of the system, components/ui/tone.ts; `outline` for a quiet one). Guide: docs/UI.md. */
import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'
import { TONE_PILL, type Tone } from './tone'

interface Props {
  children: ReactNode
  tone?: Tone | 'outline'
  className?: string
}

export default function Badge({ children, tone = 'neutral', className }: Props) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-pill text-xs font-medium',
        tone === 'outline' ? 'border border-line text-ink-muted' : TONE_PILL[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
