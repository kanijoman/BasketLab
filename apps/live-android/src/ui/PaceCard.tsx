/** Game pace: current pace, projection to the end and +/- against the habitual pace of both teams. */
import type { PaceAnalysis, TeamRef } from '../engine/types'

interface Props {
  pace?: PaceAnalysis | null
  own: TeamRef
  rival: TeamRef
}

/** Differences under this many possessions per 40 min are "como siempre". */
const SAME_PACE = 1

const fmt = (value: number) => value.toFixed(1).replace('.', ',')
const signed = (value: number) => `${value > 0 ? '+' : ''}${fmt(value)}`

function trend(delta: number): { cls: string; label: string } {
  if (Math.abs(delta) < SAME_PACE) return { cls: 'pace-same', label: 'como siempre' }
  return delta > 0 ? { cls: 'pace-fast', label: 'más rápido' } : { cls: 'pace-slow', label: 'más lento' }
}

function HabitRow({ team, habit, delta, games }: { team: TeamRef; habit: number | null; delta: number | null; games: number | null }) {
  if (habit == null || delta == null) {
    return (
      <li className="pace-row">
        <span className="pace-name">{team.name}</span>
        <span className="pace-delta">—</span>
        <span className="detail">sin dato de ritmo habitual en el paquete</span>
      </li>
    )
  }
  const { cls, label } = trend(delta)
  return (
    <li className={`pace-row ${cls}`}>
      <span className="pace-name">{team.name}</span>
      <span className="pace-delta">{signed(delta)}</span>
      <span className="detail">
        {label} · habitual {fmt(habit)}{games != null ? ` · ${games} ${games === 1 ? 'partido' : 'partidos'}` : ''}
      </span>
    </li>
  )
}

export default function PaceCard({ pace, own, rival }: Props) {
  if (!pace || !pace.reliable) {
    return (
      <section className="pace-card" aria-label="Ritmo">
        <h2>Ritmo</h2>
        <p className="detail">Calculando el ritmo… disponible a partir de los 3 minutos de juego.</p>
      </section>
    )
  }
  return (
    <section className="pace-card" aria-label="Ritmo">
      <h2>Ritmo <span className="detail">(posesiones / 40 min)</span></h2>
      <div className="pace-main">
        <div>
          <span className="pace-value">{fmt(pace.current40)}</span>
          <span className="detail"> actual</span>
        </div>
        <div className="detail">
          Proyección final {fmt(pace.projected40)} · ≈ {Math.round(pace.projected_possessions)} posesiones por equipo
        </div>
      </div>
      <ul className="pace-rows" aria-label="Ritmo frente al habitual">
        <HabitRow team={own} habit={pace.habit_own40} delta={pace.delta_own} games={pace.sample_games.own} />
        <HabitRow team={rival} habit={pace.habit_rival40} delta={pace.delta_rival} games={pace.sample_games.rival} />
      </ul>
    </section>
  )
}
