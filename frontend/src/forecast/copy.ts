// What the preview says, in Spanish (#847). The study of 26/10/2026 found no evidence that correcting a factor during a game changes what follows, so an objective is only ever «in the games where this
// happens, we win this often»: nothing here promises that making it happen wins, and the guard in `copy.test.ts` forbids «+N %», guarantees and causes. Neutral in gender: «el rival», «nuestro».
import type { BucketId, Highlight } from './scenarios'
import type { FactorKey } from './factors'
import type { Lever } from './levers'
import type { Reason } from './preview'

/** `0.5664` -> `56,6 %` (decimal comma, a space before the sign). */
export const pct = (x: number, digits = 1): string => `${(x * 100).toFixed(digits).replace('.', ',')} %`

export const FACTOR_NAMES: Record<FactorKey, string> = { efg: 'acierto de tiro', tov: 'pérdidas', orb: 'rebote ofensivo', ftr: 'tiros libres' }

/** «Nuestro acierto», «Nuestras pérdidas», «Nuestros tiros libres»: the possessive agrees with the factor. */
const POSSESSIVE: Record<'own' | 'rival', Record<FactorKey, string>> = {
  own: { efg: 'Nuestro', tov: 'Nuestras', orb: 'Nuestro', ftr: 'Nuestros' },
  rival: { efg: 'Su', tov: 'Sus', orb: 'Su', ftr: 'Sus' },
}

export const SCENARIO_TEXT: Record<BucketId, { title: string; hint: string }> = {
  lossBig: { title: 'Derrota amplia', hint: 'Perdemos por más de 10' },
  lossClose: { title: 'Derrota ajustada', hint: 'Perdemos por 10 o menos' },
  winClose: { title: 'Victoria ajustada', hint: 'Ganamos por 10 o menos' },
  winBig: { title: 'Victoria amplia', hint: 'Ganamos por más de 10' },
}

const per100 = (x: number): string => `${Math.round(x * 100)} tiros libres por cada 100 tiros de campo`
const ge = '≥'
const le = '≤'

/** What to do, with the target: `Dejar su rebote ofensivo en ≤ 28 %`. */
export function leverTitle(l: Lever): string {
  const t = l.threshold
  if (l.side === 'pace') return l.direction === 'up' ? `Subir el ritmo: ${ge} ${Math.round(t)} posesiones por 40 minutos` : `Bajar el ritmo: ${le} ${Math.round(t)} posesiones por 40 minutos`
  if (l.side === 'attack') {
    if (l.factor === 'efg') return `Subir nuestro acierto de tiro (eFG %) hasta ${ge} ${pct(t)}`
    if (l.factor === 'tov') return `Cuidar el balón: pérdidas ${le} ${pct(t)} de las posesiones`
    if (l.factor === 'orb') return `Subir nuestro rebote ofensivo hasta ${ge} ${pct(t)}`
    return `Ir más a la línea: ${ge} ${per100(t)}`
  }
  if (l.factor === 'efg') return `Limitar su acierto de tiro (eFG %) a ${le} ${pct(t)}`
  if (l.factor === 'tov') return `Forzar sus pérdidas: ${ge} ${pct(t)} de sus posesiones`
  if (l.factor === 'orb') return `Dejar su rebote ofensivo en ${le} ${pct(t, 0)}`
  return `Evitar que vayan a la línea: ${le} ${per100(t)}`
}

/** How often it happens and how often we win when it does, against how often overall. */
export const leverDetail = (l: Lever, headline: number): string =>
  `Pasa en 1 de cada 4 partidos como este. En esos partidos ganamos el ${pct(l.pWin, 0)} (en general, el ${pct(headline, 0)}).`

/** How the season went when our own games got there. */
export const leverEvidence = (l: Lever): string =>
  l.record.reached ? `Esta temporada, cuando lo hemos logrado, ganamos ${l.record.won} de ${l.record.reached}.` : 'Esta temporada todavía no lo hemos logrado.'

/** One thing that sets a kind of game apart: `Nuestro acierto de tiro: 55,1 % (esperado 51,3 %)`. */
export const highlightText = (h: Highlight): string => `${POSSESSIVE[h.side][h.factor]} ${FACTOR_NAMES[h.factor]}: ${pct(h.value)} (esperado ${pct(h.expected)})`

export function confidenceText(reason: Reason): string {
  if (reason.kind === 'small-pool') return `Hay pocos partidos de la competición para comparar (${reason.size}).`
  if (reason.games === 0) return `${reason.name} aún no ha jugado ningún partido.`
  return `${reason.name} solo ha jugado ${reason.games} ${reason.games === 1 ? 'partido' : 'partidos'}.`
}
