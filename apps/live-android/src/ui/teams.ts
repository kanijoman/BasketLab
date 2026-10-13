/** Which team goes on which side of the scoreboard, and the initials shown when a logo is missing. */
import type { TeamRef } from '../engine/types'

export interface Sides {
  home: TeamRef
  away: TeamRef
  ownIsHome: boolean
}

/**
 * The local team goes on the left and the visitor on the right, like the broadcast. ``homeId`` comes from the engine
 * (the first team of FEB's header, or the match of the package); without it our team stays on the left.
 */
export function orderTeams(own: TeamRef, rival: TeamRef, homeId?: string | null): Sides {
  return homeId != null && String(homeId) === String(rival.id)
    ? { home: rival, away: own, ownIsHome: false }
    : { home: own, away: rival, ownIsHome: true }
}

/** First letters of the first two significant words ("B.F." style abbreviations are skipped). */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  const significant = words.filter(w => w.replace(/[^\p{L}]/gu, '').length >= 3 && !w.includes('.'))
  const used = (significant.length ? significant : words).slice(0, 2)
  if (!used.length) return '?'
  return (used.length === 1 ? used[0].replace(/[^\p{L}]/gu, '').slice(0, 2) : used.map(w => w[0]).join('')).toUpperCase() || '?'
}
