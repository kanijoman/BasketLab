/** Win probability of the own team, its evolution and the levers that move it (issue #257).
 *  Experimental: it does not meet the agreed calibration yet (docs/evaluaciones/2026-10-14_probabilidad-de-victoria.md). */
import type { TeamRef, WinLever, WinProb } from '../engine/types'
import type { WinProbPoint } from './useWinProbHistory'

interface Props {
  winProb?: WinProb | null
  levers?: WinLever[] | null
  own: TeamRef
  history: WinProbPoint[]
}

const MAX_LEVERS = 3
const GAME_SECONDS = 2400
const FACTOR_LABEL: Record<string, string> = { efg: 'Acierto de tiro', tov: 'Pérdidas', orb: 'Rebote ofensivo', ftr: 'Tiros libres' }

const percent = (p: number) => `${Math.round(p * 100)} %`
const signed = (value: number) => `${value > 0 ? '+' : ''}${value.toFixed(1).replace('.', ',')}`

function leverLabel(lever: WinLever): string {
  if (lever.id === 'pace') return lever.direction === 'up' ? 'Subir el ritmo' : 'Bajar el ritmo'
  return FACTOR_LABEL[lever.id] ?? lever.id
}

function Chart({ history }: { history: WinProbPoint[] }) {
  if (history.length < 2) return null
  const end = Math.max(GAME_SECONDS, history[history.length - 1].t)
  const points = history.map(({ t, p }) => `${(t / end) * 100},${(1 - p) * 40}`).join(' ')
  return (
    <svg className="wp-chart" viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label="Evolución de la probabilidad">
      <line x1="0" y1="20" x2="100" y2="20" className="wp-chart-half" />
      <polyline points={points} className="wp-chart-line" />
    </svg>
  )
}

export default function WinProbCard({ winProb, levers, own, history }: Props) {
  if (!winProb) return null
  const top = (levers ?? []).slice(0, MAX_LEVERS)
  return (
    <section className="wp-card" aria-label="Probabilidad de victoria">
      <h2>Probabilidad de victoria <span className="badge">Experimental</span></h2>
      <div className="wp-main">
        <div>
          <span className="wp-value">{percent(winProb.p)}</span>
          <span className="detail"> {own.name}</span>
        </div>
        <div className="detail">Margen proyectado: {signed(winProb.projected_margin)}</div>
      </div>
      {!winProb.reliable && <p className="detail">Basada en el valor previo y el marcador: el partido aún dice poco.</p>}
      <Chart history={history} />
      {top.length > 0 && (
        <>
          <h3 className="wp-levers-title">Lo que más la mueve</h3>
          <ol className="wp-levers">
            {top.map(lever => {
              const proposal = lever.proposal?.find(p => p.message)
              return (
                <li key={lever.id} className="wp-lever">
                  <span className="wp-lever-name">{leverLabel(lever)}</span>
                  <span className="wp-gain">+{Math.max(1, Math.round(lever.gain * 100))} %</span>
                  {proposal && <span className="detail">{proposal.message}</span>}
                </li>
              )
            })}
          </ol>
        </>
      )}
      <p className="detail wp-note">Experimental: entre el 30 % y el 70 % puede desviarse unos ±7 puntos.</p>
    </section>
  )
}
