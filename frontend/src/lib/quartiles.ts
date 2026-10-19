/** Quartile thresholds of numeric columns, for the colour coding of `DataTable` (Q1 green … Q4 red). */
import type { QuartileMap } from '@/components/ui/DataTable'

function quantile(sorted: number[], p: number): number {
  const idx = (sorted.length - 1) * p
  const lo = Math.floor(idx)
  const hi = Math.ceil(idx)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo)
}

/** ``[q1, q2, q3]`` of every key over the rows that have a number there; ``[0, 0, 0]`` (no colouring) below four values. */
export function computeQuartileMap<T extends object>(rows: T[], keys: string[]): QuartileMap {
  const map: QuartileMap = {}
  for (const key of keys) {
    const values = rows
      .map(row => (row as Record<string, unknown>)[key])
      .filter((v): v is number => typeof v === 'number' && !Number.isNaN(v))
      .sort((a, b) => a - b)
    map[key] = values.length < 4 ? [0, 0, 0] : [quantile(values, 0.25), quantile(values, 0.5), quantile(values, 0.75)]
  }
  return map
}
