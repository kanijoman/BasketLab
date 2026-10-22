/** What to remind, and when (issue #482): one reminder per match of a team "de interés", `leadMin` minutes before the kick-off. Pure: the plugin is in `reminders.ts`. */
import { competitionOf } from '../package/filters'
import type { NextMatch } from '../package/upcoming'

export const DEFAULT_LEAD_MIN = 30
export const LEAD_OPTIONS = [15, 30, 60]

export interface Reminder {
  /** Stable 32-bit id of the match and the team (scheduling it again replaces it, it does not duplicate it). */
  id: number
  at: Date
  title: string
  body: string
  /** FEB code of the match: the notification opens it. */
  code: string
}

/** A positive 31-bit hash of the match and the team: Android notification ids are 32-bit integers. */
export function reminderId(code: string, teamId: string): number {
  let h = 17
  for (const ch of `${code}:${teamId}`) h = (Math.imul(h, 31) + ch.charCodeAt(0)) | 0
  return (h & 0x7fffffff) || 1
}

const hhmm = (d: Date) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`

/** The reminders still to come for the next matches of the teams of interest (a match with no date, or whose reminder time has passed, gives none). */
export function planReminders(next: NextMatch[], now: Date, leadMin: number = DEFAULT_LEAD_MIN): Reminder[] {
  const out: Reminder[] = []
  for (const n of next) {
    const start = n.match.start ? new Date(n.match.start) : null
    if (!start || Number.isNaN(start.getTime())) continue
    const at = new Date(start.getTime() - leadMin * 60_000)
    if (at.getTime() < now.getTime()) continue
    out.push({
      id: reminderId(n.match.code, n.ownId), at, code: n.match.code,
      title: `${n.favorite.name} juega en ${leadMin} min`,
      body: `${n.match.home.name} – ${n.match.away.name} · ${hhmm(start)} · ${competitionOf(n.round).label}`,
    })
  }
  return out
}
