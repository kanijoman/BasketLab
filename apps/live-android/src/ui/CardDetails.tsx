/** Collapsible detail of a card (issue #484): an arrow that turns over, not the words «Ver detalle». */
import { ChevronDown } from 'lucide-react'
import { useState, type ReactNode } from 'react'

export default function CardDetails({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <details className={open ? 'card-details is-open' : 'card-details'} onToggle={e => setOpen(e.currentTarget.open)}>
      <summary aria-label={open ? 'Ocultar detalle' : 'Ver detalle'} aria-expanded={open}>
        <ChevronDown size={22} aria-hidden="true" className="card-details-arrow" />
      </summary>
      {children}
    </details>
  )
}
