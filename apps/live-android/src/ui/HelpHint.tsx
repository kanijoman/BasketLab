/** A small «?» button that opens a short explanation under it (issue #225); closed by default so the screen stays clean. */
import { useId, useState, type ReactNode } from 'react'
import { CircleHelp } from 'lucide-react'

export default function HelpHint({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <span className="help-hint">
      <button type="button" className="help-button" aria-label={label} aria-expanded={open} aria-controls={id} onClick={() => setOpen(o => !o)}>
        <CircleHelp size={18} aria-hidden="true" />
      </button>
      {open && <p role="note" id={id} className="help-text">{children}</p>}
    </span>
  )
}
