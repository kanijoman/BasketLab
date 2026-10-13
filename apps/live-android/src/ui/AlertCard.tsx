import { Activity, ChartColumn, Hand, Repeat, Swords, Users, type LucideIcon } from 'lucide-react'
import type { Alert, Proposal } from '../engine/types'
import type { Verdict } from '../feedback/store'

/** Spanish label of each category the engine emits (icon below, colour in styles.css). */
export const CATEGORY_LABEL: Record<string, string> = {
  faltas: 'Faltas',
  rotacion: 'Rotación',
  rival: 'Rival',
  four_factors: 'Juego',
  gestion: 'Ritmo',
  alineacion: 'Alineación',
}

const CATEGORY_ICON: Record<string, LucideIcon> = {
  faltas: Hand, rotacion: Repeat, rival: Swords, four_factors: ChartColumn, gestion: Activity, alineacion: Users,
}

const SEVERITY_LABEL = { critical: 'Crítica', warning: 'Aviso', info: 'Info' } as const

export function formatProposal(p: Proposal): string {
  if (p.type === 'sub' && p.out_name && p.in_name) return `${p.out_name} → ${p.in_name}`
  return p.type
}

export function clockLabel(period: number, remaining: number): string {
  const mm = String(Math.floor(remaining / 60)).padStart(2, '0')
  const ss = String(remaining % 60).padStart(2, '0')
  return `${period > 4 ? `PR${period - 4}` : `Q${period}`} ${mm}:${ss}`
}

const VERDICTS: { value: Verdict; label: string }[] = [
  { value: 'seguida', label: 'Seguida' },
  { value: 'descartada', label: 'Descartada' },
  { value: 'ya_hecho', label: 'Ya hecho' },
]

/** What the staff did with the alert (issue #235): pressing the chosen answer again takes it back. */
function VerdictButtons({ verdict, onVerdict }: { verdict: Verdict | null; onVerdict: (v: Verdict | null) => void }) {
  return (
    <div className="verdicts" role="group" aria-label="¿Qué se hizo con esta alerta?">
      {VERDICTS.map(v => (
        <button key={v.value} type="button" className="secondary verdict" aria-pressed={verdict === v.value}
          onClick={() => onVerdict(verdict === v.value ? null : v.value)}>
          {v.label}
        </button>
      ))}
    </div>
  )
}

function CategoryTag({ category }: { category: string }) {
  const Icon = CATEGORY_ICON[category]
  return (
    <span className="alert-category" data-category={category}>
      {Icon && <Icon size={14} aria-hidden="true" />}
      {CATEGORY_LABEL[category] ?? category}
    </span>
  )
}

interface CardProps {
  alert: Alert
  at: string
  /** The answer of the staff; the buttons only show when somebody listens to them. */
  verdict?: Verdict | null
  onVerdict?: (verdict: Verdict | null) => void
}

export default function AlertCard({ alert, at, verdict = null, onVerdict }: CardProps) {
  return (
    <li className={`alert alert-${alert.severity}`}>
      <div className="alert-head">
        <span className="badge">{SEVERITY_LABEL[alert.severity]}</span>
        <CategoryTag category={alert.category} />
        <span className="alert-time">{at}</span>
      </div>
      <p className="alert-message">{alert.message}</p>
      {alert.proposal.length > 0 && (
        <ul className="proposals" aria-label="Propuestas">
          {alert.proposal.map((p, i) => (
            <li key={i}>{formatProposal(p)}</li>
          ))}
        </ul>
      )}
      {onVerdict && <VerdictButtons verdict={verdict} onVerdict={onVerdict} />}
    </li>
  )
}
