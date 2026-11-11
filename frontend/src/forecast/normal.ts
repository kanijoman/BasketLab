// The normal distribution for the forecast (#846). Python's `math.erf` is what the win probability of the live engine is made of (`0.5 * (1 + erf(z / sqrt 2))`), and the browser has no `erf`:
// this is the one of fdlibm (`s_erf.c`, the reference of every C math library), which agrees with it to the last bits, so that a probability never rounds differently on the page and in the engine.

const erx = 8.45062911510467529297e-01
const efx = 1.28379167095512586316e-01
const efx8 = 1.02703333676410069053e+00
const pp = [1.28379167095512558561e-01, -3.25042107247001499370e-01, -2.84817495755985104766e-02, -5.77027029648944159157e-03, -2.37630166566501626084e-05]
const qq = [1, 3.97917223959155352819e-01, 6.50222499887672944485e-02, 5.08130628187576562776e-03, 1.32494738004321644526e-04, -3.96022827877536812320e-06]
const pa = [-2.36211856075265944077e-03, 4.14856118683748331666e-01, -3.72207876035701323847e-01, 3.18346619901161753674e-01, -1.10894694282396677476e-01, 3.54783043256182359371e-02, -2.16637559486879084300e-03]
const qa = [1, 1.06420880400844228286e-01, 5.40397917702171048937e-01, 7.18286544141962662868e-02, 1.26171219808761642112e-01, 1.36370839120290507362e-02, 1.19844998467991074170e-02]
const ra = [-9.86494403484714822705e-03, -6.93858572707181764372e-01, -1.05586262253232909814e+01, -6.23753324503260060396e+01, -1.62396669462573470355e+02, -1.84605092906711035994e+02, -8.12874355063065934246e+01, -9.81432934416914548592e+00]
const sa = [1, 1.96512716674392571292e+01, 1.37657754143519042600e+02, 4.34565877475229228821e+02, 6.45387271733267880336e+02, 4.29008140027567833386e+02, 1.08635005541779435134e+02, 6.57024977031928170135e+00, -6.04244152148580987438e-02]
const rb = [-9.86494292470009928597e-03, -7.99283237680523006574e-01, -1.77579549177547519889e+01, -1.60636384855821916062e+02, -6.37566443368389627722e+02, -1.02509513161107724954e+03, -4.83519191608651397019e+02]
const sb = [1, 3.03380607434824582924e+01, 3.25792512996573918826e+02, 1.53672958608443695994e+03, 3.19985821950859553908e+03, 2.55305040643316442583e+03, 4.74528541206955367215e+02, -2.24409524465858183362e+01]

/** Horner: `c[0] + x * (c[1] + x * (c[2] + ...))`. */
const poly = (c: number[], x: number): number => c.reduceRight((acc, k) => acc * x + k, 0)

const view = new DataView(new ArrayBuffer(8))
/** The double with the low 32 bits of its mantissa cleared (what fdlibm does to `x` before squaring it, so that `z * z` is exact). */
function clearLow(x: number): number {
  view.setFloat64(0, x)
  view.setUint32(4, 0)
  return view.getFloat64(0)
}

/** The error function, as fdlibm computes it. */
export function erf(x: number): number {
  if (Number.isNaN(x)) return NaN
  if (x === Infinity) return 1
  if (x === -Infinity) return -1
  const ax = Math.abs(x)
  if (ax < 0.84375) {
    if (ax < 2 ** -28) return ax < 2 ** -1015 ? 0.125 * (8 * x + efx8 * x) : x + efx * x
    const z = x * x
    return x + x * (poly(pp, z) / poly(qq, z))
  }
  if (ax < 1.25) {
    const s = ax - 1
    const p = poly(pa, s) / poly(qa, s)
    return x >= 0 ? erx + p : -erx - p
  }
  if (ax >= 6) return x >= 0 ? 1 : -1
  const s = 1 / (ax * ax)
  const rs = ax < 1 / 0.35 ? poly(ra, s) / poly(sa, s) : poly(rb, s) / poly(sb, s)
  const z = clearLow(ax)
  const r = Math.exp(-z * z - 0.5625) * Math.exp((z - ax) * (z + ax) + rs)
  return x >= 0 ? 1 - r / ax : r / ax - 1
}

/** The normal distribution function. */
export const phi = (x: number): number => 0.5 * (1 + erf(x / Math.SQRT2))

/** The root of an increasing `f` in `[lo, hi]` to within `tol`; when `f` does not change sign there, the end it is closest to (the caller checks). */
export function bisect(f: (x: number) => number, lo: number, hi: number, tol: number): number {
  if (f(lo) >= 0) return lo
  if (f(hi) <= 0) return hi
  while (hi - lo > tol) {
    const mid = (lo + hi) / 2
    if (f(mid) < 0) lo = mid
    else hi = mid
  }
  return (lo + hi) / 2
}
