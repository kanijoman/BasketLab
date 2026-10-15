/** A note under the scoreboard ONLY when a team's formación lineup is not being watched (issue #322). The lineup of each team is
 *  watched by the engine and an illegal one is a critical alert (src/live_core/rules_lineup.py); a card that is always there said
 *  nothing and did not say whose lineup it was. Without the FEB roster of a team in the package there is nothing to watch: that is what
 *  is worth a line. */
import type { FormationStatus as Status, TeamRef } from '../engine/types'

interface Props {
  formation?: Status | null
  own: TeamRef
  rival: TeamRef
}

export default function FormationStatus({ formation, own, rival }: Props) {
  if (!formation || formation.min <= 0) return null
  const unwatched = [
    !formation.known ? own.name : null,
    formation.rival && !formation.rival.known ? rival.name : null,
  ].filter((name): name is string => name !== null)
  if (unwatched.length === 0) return null
  return (
    <p className="formation-status" data-state="unknown" role="status">
      Sin plantilla de FEB: no se vigila la alineación de formación de {unwatched.join(' ni de ')}.
    </p>
  )
}
