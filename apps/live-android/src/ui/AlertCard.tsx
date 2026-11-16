import { Activity, ChartColumn, ClipboardList, Coffee, Hand, ListChecks, Repeat, Swords, Timer, Trash2, TrendingDown, Users, type LucideIcon } from 'lucide-react'
import type { Alert, Proposal } from '../engine/types'

/** Spanish label of each category the engine emits (icon below, colour in styles.css). */
export const CATEGORY_LABEL: Record<string, string> = {
  faltas: 'Faltas',
  rotacion: 'Rotación',
  rival: 'Rival',
  four_factors: 'Juego',
  gestion: 'Ritmo',
  alineacion: 'Alineación',
  descanso: 'Descanso',
  resumen: 'Resumen',
  probabilidad: 'Probabilidad',
}

const CATEGORY_ICON: Record<string, LucideIcon> = {
  faltas: Hand, rotacion: Repeat, rival: Swords, four_factors: ChartColumn, gestion: Activity, alineacion: Users, descanso: Coffee, resumen: ListChecks,
  probabilidad: TrendingDown,
}

const SEVERITY_LABEL = { critical: 'Crítica', warning: 'Aviso', info: 'Info' } as const

/** Icon of each proposal kind; a kind this app does not know yet gets the tactic icon. */
const PROPOSAL_ICON: Record<string, LucideIcon> = { sub: Repeat, timeout: Timer, tactic: ClipboardList }

function timeoutText(left: unknown): string {
  if (typeof left !== 'number') return 'Tiempo muerto'
  if (left <= 0) return 'Tiempo muerto · no quedan'
  return left === 1 ? 'Tiempo muerto · queda 1' : `Tiempo muerto · quedan ${left}`
}

/** One line of text per proposal kind (issue #240); an unknown kind shows its message, or its type as a last resort. */
export function formatProposal(p: Proposal): string {
  const message = typeof p.message === 'string' ? p.message : ''
  if (p.type === 'sub' && p.out_name && p.in_name) return `${p.out_name} → ${p.in_name}`
  if (p.type === 'timeout') return timeoutText(p.left)
  if (p.type === 'tactic' && message) return typeof p.player_name === 'string' ? `${p.player_name}: ${message}` : message
  return message || p.type
}

export function clockLabel(period: number, remaining: number): string {
  const mm = String(Math.floor(remaining / 60)).padStart(2, '0')
  const ss = String(remaining % 60).padStart(2, '0')
  return `${period > 4 ? `PR${period - 4}` : `Q${period}`} ${mm}:${ss}`
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
  /** Dismiss the alert (issue #933); the bin only shows when somebody listens to it. */
  onDismiss?: () => void
  /** Arrived with the latest change of the list: enters with a highlight (issue #312). */
  fresh?: boolean
}

export default function AlertCard({ alert, at, onDismiss, fresh = false }: CardProps) {
  return (
    <li className={`alert alert-${alert.severity}${fresh ? ' alert-new' : ''}`}>
      <div className="alert-head">
        <span className="badge">{SEVERITY_LABEL[alert.severity]}</span>
        <CategoryTag category={alert.category} />
        <span className="alert-time">{at}</span>
        {onDismiss && (
          <button type="button" className="secondary icon-button alert-dismiss" aria-label="Descartar aviso" onClick={onDismiss}>
            <Trash2 size={18} aria-hidden="true" />
          </button>
        )}
      </div>
      <p className="alert-message">{alert.message}</p>
      {alert.proposal.length > 0 && (
        <ul className="proposals" aria-label="Propuestas">
          {alert.proposal.map((p, i) => {
            const Icon = PROPOSAL_ICON[p.type] ?? ClipboardList
            return (
              <li key={i} data-kind={p.type}>
                <Icon size={14} aria-hidden="true" className="proposal-icon" />
                {formatProposal(p)}
              </li>
            )
          })}
        </ul>
      )}
    </li>
  )
}
