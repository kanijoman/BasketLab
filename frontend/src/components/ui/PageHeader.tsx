/** The head of a page (issue #190): its only h1, a subtitle (the competition, usually) and its actions on the right. Guide: docs/UI.md. */
import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Props {
  title: ReactNode
  subtitle?: ReactNode
  icon?: LucideIcon
  actions?: ReactNode
  className?: string
}

export default function PageHeader({ title, subtitle, icon: Icon, actions, className }: Props) {
  return (
    <header className={cn('flex flex-wrap items-start gap-3', className)}>
      <div className="min-w-0">
        <h1 className="flex items-center gap-2 text-2xl font-bold text-ink">
          {Icon && <Icon className="h-6 w-6 shrink-0 text-accent-text" aria-hidden="true" />}
          {title}
        </h1>
        {subtitle && <p className="mt-0.5 text-sm text-ink-muted">{subtitle}</p>}
      </div>
      {actions && <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}
