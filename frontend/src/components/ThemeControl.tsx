/** Where to choose the theme of the web (issue #188): light (the default), dark or the device's. */
import { Monitor, Moon, Sun, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme, type ThemePreference } from '@/lib/theme'

const OPTIONS: { value: ThemePreference; label: string; icon: LucideIcon }[] = [
  { value: 'light', label: 'Claro', icon: Sun },
  { value: 'dark', label: 'Oscuro', icon: Moon },
  { value: 'system', label: 'Sistema', icon: Monitor },
]

export default function ThemeControl() {
  const { preference, setPreference } = useTheme()
  return (
    <div role="radiogroup" aria-label="Tema" className="inline-flex items-center rounded-pill border border-line bg-canvas p-0.5">
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const checked = preference === value
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={label}
            title={label}
            onClick={() => setPreference(value)}
            className={cn('rounded-pill p-1.5 transition-colors',
              checked ? 'bg-surface text-accent-text shadow-card' : 'text-ink-muted hover:text-ink')}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        )
      })}
    </div>
  )
}
