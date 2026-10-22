/** The scoreboard: local team on the left, visitor on the right, with crests and the clock in the middle. */
import { useEffect, useRef } from 'react'
import type { TeamRef } from '../engine/types'
import TeamLogo from './TeamLogo'
import { orderTeams } from './teams'

interface Props {
  own: TeamRef
  rival: TeamRef
  /** Local team id from the engine (null/undefined: unknown). */
  homeId?: string | null
  score?: Record<string, number>
  clock: string
  /** The last line received from the feed (``snapshot.last_event``), shown under the score (issue #490). */
  lastEvent?: { text?: string; period?: number; remaining?: number } | null
}

/** The points of a team; they flash when they change (issue #312), not at the first paint. Keyed by the value so the animation replays. */
function Points({ value }: { value: number }) {
  const previous = useRef(value)
  const changed = previous.current !== value
  useEffect(() => { previous.current = value }, [value])
  return <span key={value} className={changed ? 'pts bump' : 'pts'}>{value}</span>
}

export default function Scoreboard({ own, rival, homeId, score, clock, lastEvent }: Props) {
  const { home, away } = orderTeams(own, rival, homeId)
  const side = (team: TeamRef) => (
    <div className="team">
      <TeamLogo team={team} size={44} />
      <span className="name">{team.name}</span>
      <Points value={score?.[team.id] ?? 0} />
    </div>
  )
  return (
    <header className="scoreboard">
      {side(home)}
      <div className="clock">{clock}</div>
      {side(away)}
      {lastEvent?.text && (
        <p className="last-event" aria-live="off" aria-label="Última jugada del feed">
          <span className="last-clock">{clock}</span>{lastEvent.text}
        </p>
      )}
    </header>
  )
}
