/**
 * The tabs of a page (issue #190): a tab list (role tablist) with the arrows, Home and End of the keyboard; `trailing` puts a control of the
 * page at the end of the row (as the basic/advanced switch of the rivals in Equipo). The page shows the panel of the open tab. Guide: docs/UI.md.
 */
import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface TabItem<T extends string> {
  id: T
  label: string
  icon?: LucideIcon
}

interface Props<T extends string> {
  label: string
  tabs: TabItem<T>[]
  value: T
  onChange: (id: T) => void
  trailing?: ReactNode
  className?: string
}

export default function Tabs<T extends string>({ label, tabs, value, onChange, trailing, className }: Props<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  function move(event: KeyboardEvent, from: number) {
    const last = tabs.length - 1
    const targets: Record<string, number> = { ArrowRight: from === last ? 0 : from + 1, ArrowLeft: from === 0 ? last : from - 1, Home: 0, End: last }
    const to = targets[event.key]
    if (to === undefined) return
    event.preventDefault()
    onChange(tabs[to].id)
    refs.current[to]?.focus()
  }

  return (
    <div className={cn('flex items-center gap-1 border-b border-line', className)}>
      <div role="tablist" aria-label={label} className="flex items-center gap-1 overflow-x-auto">
        {tabs.map(({ id, label: name, icon: Icon }, i) => {
          const selected = id === value
          return (
            <button
              key={id}
              ref={el => { refs.current[i] = el }}
              type="button"
              role="tab"
              aria-selected={selected}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(id)}
              onKeyDown={e => move(e, i)}
              className={cn('-mb-px flex shrink-0 items-center gap-1.5 border-b-2 px-4 py-2 text-sm font-medium transition-colors',
                selected ? 'border-accent text-accent-text' : 'border-transparent text-ink-faint hover:text-ink')}
            >
              {Icon && <Icon className="h-3.5 w-3.5" aria-hidden="true" />}
              {name}
            </button>
          )
        })}
      </div>
      {trailing && <div className="ml-auto mb-1 flex items-center">{trailing}</div>}
    </div>
  )
}
