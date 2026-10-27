/** A panel of the page (issue #190) over the .card class: an optional title (h2) with its actions, and the content. Guide: docs/UI.md. */
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  title?: ReactNode
  actions?: ReactNode
  /** `none` for a table or a chart that reaches the edges */
  padding?: 'none' | 'md'
  className?: string
  children: ReactNode
}

export default function Card({ title, actions, padding = 'md', className, children }: Props) {
  return (
    <section className={cn('card', padding === 'md' && 'p-4', className)}>
      {(title || actions) && (
        <header className={cn('flex items-center gap-3', padding === 'none' ? 'border-b border-line px-4 py-3' : 'mb-3')}>
          {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
          {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}
