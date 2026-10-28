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
