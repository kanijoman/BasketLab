// What the preview says, in Spanish (#847). The study of 26/10/2026 found no evidence that correcting a factor during a game changes what follows, so an objective is only ever «in the games where this
// happens, we win this often»: nothing here promises that making it happen wins, and the guard in `copy.test.ts` forbids «+N %», guarantees and causes. Neutral in gender: «el rival», «nuestro».
import type { BucketId, Highlight } from './scenarios'
import type { FactorKey } from './factors'
import type { Band, BandInfo, Lever } from './levers'
import type { Reason } from './preview'
import type { VariableId } from './projection/variables'

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

/** Every variable of the projection by name: «Nuestras pérdidas», «Su acierto de tiro (eFG)». */
export const VARIABLE_NAMES: Record<VariableId, string> = {
  'game.possessions': 'Posesiones',
  'own.points': 'Nuestros puntos', 'rival.points': 'Sus puntos',
  'own.oer': 'Nuestros puntos por 100 posesiones', 'rival.oer': 'Sus puntos por 100 posesiones',
  'own.efg': 'Nuestro acierto de tiro (eFG)', 'rival.efg': 'Su acierto de tiro (eFG)',
  'own.tov': 'Nuestras pérdidas', 'rival.tov': 'Sus pérdidas',
  'own.orb': 'Nuestro rebote ofensivo', 'rival.orb': 'Su rebote ofensivo',
  'own.ftr': 'Nuestros tiros libres por cada 100 tiros de campo', 'rival.ftr': 'Sus tiros libres por cada 100 tiros de campo',
}

/** «nuestras pérdidas», «las posesiones»: the name inside a sentence. */
export const variableInSentence = (id: VariableId): string => (id === 'game.possessions' ? 'las posesiones' : VARIABLE_NAMES[id].charAt(0).toLowerCase() + VARIABLE_NAMES[id].slice(1))

const isRatio = (id: VariableId): boolean => /\.(efg|tov|orb)$/.test(id)

/** A value of a variable as the page writes it: a share with its sign (`21,2 %`), the free throws per 100 shots, the points and the possessions whole. */
export function valueText(id: VariableId, x: number): string {
  if (isRatio(id)) return pct(x)
  if (id.endsWith('.ftr')) return String(Math.round(x * 100))
  return id.endsWith('.oer') ? (Math.round(x * 10) / 10).toFixed(1).replace('.', ',') : String(Math.round(x))
}

type InfoLines = { title: string; summary: string; record: string; caveat: string }
const won = (b: { reached: number; won: number }) => `ganamos ${b.won} de ${b.reached}`

/** The pace as information (#857): what is expected, how the season went at a slow and at a fast pace, and that nothing says it changes the result. */
function paceLines(pace: BandInfo): InfoLines {
  const slow = `ritmo lento (${le} ${Math.round(pace.low.threshold)} posesiones)`
  const fast = `ritmo alto (${ge} ${Math.round(pace.high.threshold)})`
  const [s, f] = [pace.low.record, pace.high.record]
  const record = !s.reached && !f.reached ? `Esta temporada aún no hemos jugado a ${slow} ni a ${fast}.`
    : !s.reached ? `Esta temporada aún no hemos jugado a ${slow} y a ${fast} ${won(f)}.`
    : !f.reached ? `Esta temporada, a ${slow} ${won(s)} y aún no hemos jugado a ${fast}.`
    : `Esta temporada, a ${slow} ${won(s)} y a ${fast} ${won(f)}.`
  return { title: 'Ritmo (informativo)', summary: `Se espera un partido de unas ${Math.round(pace.expected)} posesiones por 40 minutos.`, record, caveat: 'Es solo una referencia: no se ha podido comprobar que el ritmo cambie la probabilidad de ganar.' }
}

/** A factor as information (#941, our turnovers): what is expected, the season at the low and at the high end, and that knowing it did not sharpen the probability of winning. */
function factorLines(info: BandInfo): InfoLines {
  const of = info.variable.startsWith('own.') ? 'de nuestras posesiones' : 'de sus posesiones'
  const unit = isRatio(info.variable) ? ` ${of}` : ' por cada 100 tiros de campo'
  const band = (sign: string, b: Band) => `con ${sign} ${valueText(info.variable, b.threshold)}: ${b.record.reached ? won(b.record) : 'ninguno todavía'}`
  return {
    title: `${VARIABLE_NAMES[info.variable]} (informativo)`, summary: `Lo esperado en este partido: ${valueText(info.variable, info.expected)}${unit}.`,
    record: `Esta temporada, ${band(le, info.low)}; ${band(ge, info.high)}.`,
    caveat: `Es solo una referencia: en la evaluación, conocer ${variableInSentence(info.variable)} no ha afinado la probabilidad de ganar.`,
  }
}

/** What the page tells as information (`BandInfo`): its title, what is expected, the season and why there is no probability. */
export const infoLines = (info: BandInfo): InfoLines => (info.variable === 'game.possessions' ? paceLines(info) : factorLines(info))

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
