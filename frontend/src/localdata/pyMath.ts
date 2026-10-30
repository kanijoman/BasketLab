// Python's `round(x, n)` (what the API rounds its advanced figures with): to the nearest, exact ties to the even digit.
// `Math.round` rounds every tie up and `toFixed` rounds the ties of the exact binary value up, so both disagree on 12.25 → 12.2.
export function pyRound(x: number, digits: number): number {
  if (!Number.isFinite(x)) return x
  const sign = x < 0 || Object.is(x, -0) ? -1 : 1
  const abs = Math.abs(x)
  const exact = abs.toFixed(100)                                  // the exact decimal expansion of the double
  const dot = exact.indexOf('.')
  const rest = exact.slice(dot + 1 + digits)
  if (!/^50*$/.test(rest)) return sign * Number(abs.toFixed(digits))
  const kept = exact.slice(0, dot + 1 + digits).replace(/\.$/, '')
  const lastDigit = Number(kept[kept.length - 1])
  return sign * (lastDigit % 2 === 0 ? Number(kept) : Number(abs.toFixed(digits)))
}

// NumPy's `np.sum` of a float array: pairwise (blocks of eight accumulators up to 128 values, halves above), which is not the sequential sum and can differ in the last bit.
function npSum(values: number[], from = 0, count = values.length): number {
  if (count < 8) {
    let sum = 0
    for (let i = 0; i < count; i++) sum += values[from + i]
    return sum
  }
  if (count <= 128) {
    const r = values.slice(from, from + 8)
    let i = 8
    for (; i < count - (count % 8); i += 8) for (let j = 0; j < 8; j++) r[j] += values[from + i + j]
    let sum = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]))
    for (; i < count; i++) sum += values[from + i]
    return sum
  }
  let half = Math.floor(count / 2)
  half -= half % 8
  return npSum(values, from, half) + npSum(values, from + half, count - half)
}

/** `np.mean(values)` */
export const npMean = (values: number[]): number => npSum(values) / values.length

/** `np.std(values)` (population, ddof = 0), as NumPy computes it: the squared deviations from the mean, summed pairwise. */
export function npStd(values: number[]): number {
  const mean = npMean(values)
  return Math.sqrt(npSum(values.map(value => (value - mean) * (value - mean))) / values.length)
}
