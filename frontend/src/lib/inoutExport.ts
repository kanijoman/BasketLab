// The export of IN/OUT (issue #759). The page has no table, only cards, so the CSV is made of the figures the cards show: one row per statistic with the ON block, the OFF block and
// their difference (ON − OFF). Whatever is better, the difference is the plain subtraction: «DRtg» lower is better and the CSV does not interpret it.
import type { InOutStatBlock } from '@/api/client'

export interface InOutStatDef {
  key: string
  /** The label of the card (`StatCard` in `pages/InOutPage.tsx`), so the file says what the screen says. */
  label: string
}

export const INOUT_STATS: InOutStatDef[] = [
  { key: 'net_rating', label: 'Net Rating' }, { key: 'offensive_rating', label: 'ORtg' }, { key: 'defensive_rating', label: 'DRtg' }, { key: 'possessions_per_40', label: 'Poss/40min' },
  { key: 'points_for', label: 'Pts a favor' }, { key: 'points_against', label: 'Pts en contra' }, { key: 'efg_percentage', label: 'eFG%' }, { key: 'true_shooting', label: 'TS%' },
  { key: 'fg2_made', label: 'T2 anotados' }, { key: 'fg2_attempts', label: 'T2 intentados' }, { key: 'fg2_percentage', label: 'T2 %' },
  { key: 'fg3_made', label: 'T3 anotados' }, { key: 'fg3_attempts', label: 'T3 intentados' }, { key: 'fg3_percentage', label: 'T3 %' },
  { key: 'ft_made', label: 'TL anotados' }, { key: 'ft_attempts', label: 'TL intentados' }, { key: 'ft_percentage', label: 'TL %' },
  { key: 'three_point_rate', label: '3Pr' }, { key: 'free_throw_rate', label: 'FTr' },
  { key: 'offensive_rebound_rate', label: 'OR%' }, { key: 'defensive_rebound_rate', label: 'DR%' }, { key: 'off_rebounds', label: 'REB-O' }, { key: 'def_rebounds', label: 'REB-D' },
  { key: 'assist_rate', label: '%AST' }, { key: 'turnover_rate', label: '%TO' }, { key: 'assists', label: 'AST' }, { key: 'turnovers', label: 'TOV' },
  { key: 'steals', label: 'STL' }, { key: 'blocks', label: 'BLK' }, { key: 'minutes', label: 'Minutos' },
]

/** A figure, or `null` when the block does not have it (a zero is a figure). */
const figure = (block: InOutStatBlock, key: string): number | null => {
  const value = block[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** `a − b` without the noise of the binary floats (105.4 − 100 is 5.4), and empty when either is missing: never a zero that says something. */
const difference = (a: number | null, b: number | null): number | null => (a === null || b === null ? null : Math.round((a - b) * 1e6) / 1e6)

export interface InOutRow { stat: string; on: number | null; off: number | null; diff: number | null }
export interface InOutVsRow { stat: string; a: number | null; b: number | null; diff: number | null }

/** The rows of a player: ON, OFF and ON − OFF. */
export function inoutRows(on: InOutStatBlock, off: InOutStatBlock): InOutRow[] {
  return INOUT_STATS.map(({ key, label }) => {
    const a = figure(on, key)
    const b = figure(off, key)
    return { stat: label, on: a, off: b, diff: difference(a, b) }
  })
}

/** The rows of «IN vs IN»: the ON block of two players and the first minus the second. */
export function inoutVsRows(first: InOutStatBlock, second: InOutStatBlock): InOutVsRow[] {
  return INOUT_STATS.map(({ key, label }) => {
    const a = figure(first, key)
    const b = figure(second, key)
    return { stat: label, a, b, diff: difference(a, b) }
  })
}
