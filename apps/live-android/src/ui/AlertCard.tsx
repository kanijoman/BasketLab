import type { Alert, Proposal } from '../engine/types'

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

export default function AlertCard({ alert, at }: { alert: Alert; at: string }) {
  return (
    <li className={`alert alert-${alert.severity}`}>
      <div className="alert-head">
        <span className="badge">{SEVERITY_LABEL[alert.severity]}</span>
        <span className="alert-category">{alert.category}</span>
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
    </li>
  )
}
