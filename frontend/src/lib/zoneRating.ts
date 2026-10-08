/** League-relative rating of a shooting zone: above / around / below the league average. */
export type ZoneRating = 'above' | 'average' | 'below' | 'none' | 'unknown'

export const RATING_COLOR: Record<'above' | 'average' | 'below', string> = {
  above: '#2E9E4F',
  average: '#E0A800',
  below: '#D64545',
}

export const RATING_LABEL: Record<'above' | 'average' | 'below', string> = {
  above: 'Por encima de la liga',
  average: 'En el promedio',
  below: 'Por debajo de la liga',
}

const NO_DATA = '#6b7280'

export function ratingColor(rating?: ZoneRating): string {
  return rating === 'above' || rating === 'average' || rating === 'below' ? RATING_COLOR[rating] : NO_DATA
}

export function ratingTextClass(rating?: ZoneRating): string {
  switch (rating) {
    case 'above': return 'text-green-400'
    case 'average': return 'text-yellow-400'
    case 'below': return 'text-red-400'
    default: return 'text-ink-secondary'
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
