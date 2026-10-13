/** Formación players on court against the minimum of the competition (issue #272), under the scoreboard. */
import type { FormationStatus as Status } from '../engine/types'

const LINEUP = 5

export default function FormationStatus({ formation }: { formation?: Status | null }) {
  if (!formation || formation.min <= 0) return null
  if (!formation.known) {
    return (
      <p className="formation-status" data-state="unknown" role="status">
        Sin plantilla de FEB: no se vigila la alineación de formación.
      </p>
    )
  }
  const { min, unknown, players } = formation
  const count = formation.on_court ?? 0
  const incomplete = players < LINEUP                     // a substitution is in progress: not a violation yet
  const bad = !incomplete && count + unknown < min        // even the players without data could not reach the minimum
  const state = bad ? 'bad' : incomplete ? 'pending' : count <= min ? 'limit' : 'ok'
  const notes = [
    unknown > 0 ? `${unknown} sin datos` : null,
    incomplete ? 'cambio en curso' : null,
    bad ? 'por debajo del mínimo' : null,
  ].filter(Boolean)
  return (
    <p className="formation-status" data-state={state} role={bad ? 'alert' : 'status'}>
      Formación en pista: {count} (mínimo {min}){notes.length > 0 && ` · ${notes.join(' · ')}`}
    </p>
  )
}
