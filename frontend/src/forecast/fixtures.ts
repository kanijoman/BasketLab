// The matches a team has left (#849): what the page lists after choosing the team, each with the rival and where it is played, from the side of the team.
import type { Calendar } from '@/webdata/calendar'
import type { GameResult } from './gameLog'
import { pendingFixtures } from './seasonSim'
import type { Court } from './winProb'

export interface TeamFixture {
  code: string
  round: number
  /** `YYYY-MM-DDTHH:MM`, Madrid time; `null` when the calendar has no kick-off. */
  start: string | null
  /** `own`: the team plays at home; `rival`: it plays away. */
  court: Court
  rival: string
  rivalName: string
  /** A match being played right now. */
  live: boolean
}

/** The matches still to play of `team`, in the order they will be played (by kick-off, those without one at the end, then by round). */
export function teamFixtures(games: GameResult[], calendar: Calendar, team: string): TeamFixture[] {
  return pendingFixtures(games, calendar)
    .filter(f => f.home === team || f.away === team)
    .map((f): TeamFixture => {
      const home = f.home === team
      return { code: f.code, round: f.round, start: f.start, court: home ? 'own' : 'rival', rival: home ? f.away : f.home, rivalName: home ? f.awayName : f.homeName, live: f.kind === 'live' }
    })
    .sort((a, b) => (a.start ?? '9999').localeCompare(b.start ?? '9999') || a.round - b.round)
}

/** A match that began less than this long ago still counts as the next one (it is being played or has just ended). */
const STARTED = 3 * 60 * 60_000

/** The fixture the page opens on: the first that has not started (Madrid time is read as UTC: only the order matters), the last when all are in the past, none when there are no fixtures. */
export function nextFixture(list: TeamFixture[], now: number): TeamFixture | null {
  if (!list.length) return null
  return list.find(f => f.live || f.start === null || Date.parse(`${f.start}:00Z`) >= now - STARTED) ?? list[list.length - 1]
}
