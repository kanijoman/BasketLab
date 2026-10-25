/** A dropdown that looks like the rest of the app (issue #571). The system `<select>` opens as a plain list of radio buttons on Android; this keeps the same contract
 *  (a label, a value, options, `onChange`) with a button that shows the chosen option and a list below it, usable with touch and keyboard. */
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'

export interface SelectOption {
  value: string
  label: string
}

interface Props {
  label: string
  value: string
  options: SelectOption[]
  onChange: (value: string) => void
  className?: string
}

export default function Select({ label, value, options, onChange, className }: Props) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const id = useId()
  const chosen = Math.max(0, options.findIndex(o => o.value === value))

  useEffect(() => {
    if (!open) return
    const outside = (e: Event) => { if (root.current && !root.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', outside)
    document.addEventListener('touchstart', outside)
    return () => { document.removeEventListener('mousedown', outside); document.removeEventListener('touchstart', outside) }
  }, [open])

  const openAt = (index: number) => { setActive(index); setOpen(true) }
  const choose = (index: number) => { setOpen(false); if (options[index]) onChange(options[index].value) }
  const onKey = (e: KeyboardEvent) => {
    const move = (to: number) => { e.preventDefault(); if (open) setActive(Math.min(Math.max(to, 0), options.length - 1)); else openAt(chosen) }
    if (e.key === 'ArrowDown') move(open ? active + 1 : chosen)
    else if (e.key === 'ArrowUp') move(open ? active - 1 : chosen)
    else if (e.key === 'Escape' && open) { e.preventDefault(); setOpen(false) }
    else if ((e.key === 'Enter' || e.key === ' ') && open) { e.preventDefault(); choose(active) }
  }

  return (
    <div className={`select-field${className ? ` ${className}` : ''}`} ref={root}>
      <span className="select-label" id={`${id}-label`}>{label}</span>
      <button type="button" className="select-box secondary" role="combobox" aria-label={label} data-value={value} aria-haspopup="listbox" aria-expanded={open}
        aria-controls={`${id}-list`} onClick={() => (open ? setOpen(false) : openAt(chosen))} onKeyDown={onKey}>
        <span className="select-value">{options[chosen]?.label ?? ''}</span>
        <span className="select-chevron" aria-hidden="true">▾</span>
      </button>
      {open && (
        <ul className="select-list" role="listbox" id={`${id}-list`} aria-labelledby={`${id}-label`}>
          {options.map((o, i) => (
            <li key={o.value} role="option" data-value={o.value} aria-selected={i === chosen} className={i === active ? 'active' : undefined}
              onMouseEnter={() => setActive(i)} onClick={() => choose(i)}>
              {o.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
