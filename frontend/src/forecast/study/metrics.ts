// The scores of the walk-forward evaluation (#851): what a probability is judged with. Pure functions, the way the study and its tests share them.

const FLOOR = 1e-12

/** Log loss of a forecast `p` of an event that happened (`y` = 1), did not (0) or half did (0.5, a tie). Capped so that a certain mistake is finite. */
export const logLoss = (p: number, y: number): number => -(y * Math.log(Math.max(p, FLOOR)) + (1 - y) * Math.log(Math.max(1 - p, FLOOR)))

export const brier = (p: number, y: number): number => (p - y) ** 2

/** Brier over several classes: the sum over the classes of (probability - 1 if it happened else 0)^2. */
export const multiclassBrier = (probs: number[], actual: number): number => probs.reduce((s, p, i) => s + (p - (i === actual ? 1 : 0)) ** 2, 0)

/** Ranked probability score of an ordered distribution: the mean over the cut points of the squared gap between the cumulative forecast and the cumulative outcome. */
export function rps(probs: number[], actual: number): number {
  let forecast = 0
  let sum = 0
  for (let i = 0; i < probs.length - 1; i++) {
    forecast += probs[i]
    sum += (forecast - (actual <= i ? 1 : 0)) ** 2
  }
  return sum / (probs.length - 1)
}

/** Means and rates of what is added: one row of a table of results. */
export class Scores {
  n = 0
  private readonly sums = new Map<string, number>()

  add(values: Record<string, number | boolean>): void {
    this.n++
    for (const [key, value] of Object.entries(values)) this.sums.set(key, (this.sums.get(key) ?? 0) + Number(value))
  }

  mean(key: string): number {
    return this.n ? (this.sums.get(key) ?? 0) / this.n : NaN
  }

  rate(key: string): number {
    return this.mean(key)
  }
}

export interface CalibrationBin { from: number; to: number; n: number; predicted: number; actual: number }

/** The forecasts in `bins` equal bins of probability: how many, their mean and the mean of what happened. Empty bins are left out. */
export function calibrationTable(forecasts: { p: number; y: number }[], bins: number): CalibrationBin[] {
  const grouped: { p: number; y: number }[][] = Array.from({ length: bins }, () => [])
  for (const f of forecasts) grouped[Math.min(bins - 1, Math.floor(f.p * bins))].push(f)
  return grouped.flatMap((group, i) => group.length
    ? [{ from: i / bins, to: (i + 1) / bins, n: group.length, predicted: group.reduce((s, f) => s + f.p, 0) / group.length, actual: group.reduce((s, f) => s + f.y, 0) / group.length }]
    : [])
}
