/**
 * Choose one of a few (issue #190): a group of radios (role radiogroup) with the arrows of the keyboard; only the chosen option takes the Tab.
 * With `iconOnly` every option shows its icon and keeps its label as name and tooltip. Guide: docs/UI.md.
 */
import { useRef, type KeyboardEvent } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SegmentOption<T extends string> {
  value: T
  label: string
  icon?: LucideIcon
}

interface Props<T extends string> {
  /** The name of the group for the screen reader */
  label: string
  options: SegmentOption<T>[]
  value: T
  onChange: (value: T) => void
  size?: 'sm' | 'md'
  iconOnly?: boolean
  className?: string
}

const STEP: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }

export default function SegmentedControl<T extends string>({ label, options, value, onChange, size = 'sm', iconOnly = false, className }: Props<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const chosen = Math.max(0, options.findIndex(o => o.value === value))

  function move(event: KeyboardEvent, from: number) {
    const step = STEP[event.key]
    if (!step) return
    event.preventDefault()
    const next = (from + step + options.length) % options.length
    onChange(options[next].value)
    refs.current[next]?.focus()
  }

  return (
    <div role="radiogroup" aria-label={label} className={cn('inline-flex overflow-hidden rounded-lg border border-line', className)}>
      {options.map(({ value: v, label: name, icon: Icon }, i) => {
        const checked = i === chosen
        return (
          <button
            key={v}
            ref={el => { refs.current[i] = el }}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={iconOnly ? name : undefined}
            title={iconOnly ? name : undefined}
            tabIndex={checked ? 0 : -1}
            onClick={() => onChange(v)}
            onKeyDown={e => move(e, i)}
            className={cn('inline-flex items-center gap-1.5 font-medium transition-colors',
              size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm', iconOnly && (size === 'sm' ? 'px-1.5' : 'px-2'),
              checked ? 'bg-accent/30 text-accent-text' : 'text-ink-muted hover:bg-surface-raised hover:text-ink')}
          >
            {Icon && <Icon className={size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} aria-hidden="true" />}
            {!iconOnly && name}
          </button>
        )
      })}
    </div>
  )
}
