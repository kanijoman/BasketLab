// The calendar of a competition (issues #842, #845): every match with its round, kick-off and, once played, its score. Published for the competitions of the newest season only; it is read from the
// federations on every publication, so it can be newer than the rows (a finished result the rows do not have yet, a match being played: `live`).
import { loadWebSection } from './client'

export interface CalendarTeam { id: string; name: string }

export interface CalendarMatch {
  /** The code of the match in its calendar (FEB: the match code; FBCYL: `fbcyl-<idMatch>`). */
  code: string
  /** The `_id` of the game of this match: the `match_id` of its rows, to tell which results the rows already have. */
  match_id: string
  round: number
  /** `result` (it has a score), `scheduled`, or `live` (a result of the FEB that the archive does not have and the live feed says is being played: not played yet). */
  kind: 'result' | 'scheduled' | 'live'
  /** `YYYY-MM-DDTHH:MM`, Madrid time; `null` for a FEB result (the page does not give it). */
  start: string | null
  home: CalendarTeam
  away: CalendarTeam
  /** `[home, away]` of a result, otherwise `null`. */
  score: [number, number] | null
}

export interface Calendar {
  format: number
  collection: string
  league: 'feb' | 'fbcyl'
  games: number
  /** FBCYL groups may end a game tied (a tie is half a win); in the FEB it is always `false`. */
  ties_allowed: boolean
  matches: CalendarMatch[]
}

/** The calendar of a competition. @throws WebDataUnavailable it has none published (the pages that need it stay hidden). */
export const loadWebCalendar = (collection: string): Promise<Calendar> =>
  loadWebSection<Calendar>('calendar', collection, 'Esta competición no tiene el calendario publicado.')
