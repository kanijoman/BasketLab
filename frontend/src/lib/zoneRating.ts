import type { ChartTheme } from './chartTheme'

/** League-relative rating of a shooting zone: above / around / below the league average. */
export type ZoneRating = 'above' | 'average' | 'below' | 'none' | 'unknown'

/** The colour of each rating in the theme in use: the data tones (good, borderline, bad) of design/tokens.css (issue #196). */
export const zoneColours = (theme: ChartTheme): Record<'above' | 'average' | 'below', string> =>
  ({ above: theme.ok, average: theme.warn, below: theme.bad })

export const RATING_LABEL: Record<'above' | 'average' | 'below', string> = {
  above: 'Por encima de la liga',
  average: 'En el promedio',
  below: 'Por debajo de la liga',
}

export function ratingColor(rating: ZoneRating | undefined, theme: ChartTheme): string {
  return rating === 'above' || rating === 'average' || rating === 'below' ? zoneColours(theme)[rating] : theme.faint
}

export function ratingTextClass(rating?: ZoneRating): string {
  switch (rating) {
    case 'above': return 'text-ok'
    case 'average': return 'text-warn'
    case 'below': return 'text-bad'
    default: return 'text-ink-muted'
  }
}

/** Rate a value against league quartiles (used where only quartiles are available). */
export function ratingFromQuartiles(
  value: number,
  q?: { q1?: number | null; q2?: number | null; q3?: number | null },
): ZoneRating {
  if (!q || q.q1 == null || q.q3 == null) return 'unknown'
  if (value > q.q3) return 'above'
  if (value < q.q1) return 'below'
  return 'average'
}
