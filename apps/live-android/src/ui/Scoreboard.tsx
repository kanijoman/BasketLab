/** The scoreboard: local team on the left, visitor on the right, with crests and the clock in the middle. */
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
}

export default function Scoreboard({ own, rival, homeId, score, clock }: Props) {
  const { home, away } = orderTeams(own, rival, homeId)
  const side = (team: TeamRef) => (
    <div className="team">
      <TeamLogo team={team} size={44} />
      <span className="name">{team.name}</span>
      <span className="pts">{score?.[team.id] ?? 0}</span>
      {team.id === own.id && <span className="own-tag">Tu equipo</span>}
    </div>
  )
  return (
    <header className="scoreboard">
      {side(home)}
      <div className="clock">{clock}</div>
      {side(away)}
    </header>
  )
}
