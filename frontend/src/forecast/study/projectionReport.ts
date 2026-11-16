// The section of the report on the projection of a match (#938): markdown in Spanish with the decimal comma, from `walkForwardProjection`, `leaguePaceSlopes` and `splitHalf`. The support of
// a variable is the rule the objectives were held to on 11/11/2026 (#857): in the games where its condition happened, the probability foreseen is within two standard errors of how often the
// team won, in every family with enough cases, and it does not do worse than the headline there.
import type { ResponseKey, Slopes } from '../projection/paceResponse'
import { RESPONSE_KEYS } from '../projection/paceResponse'
import { VARIABLES, type VariableId } from '../projection/variables'
import { brier } from './metrics'
import type { ConditionRecord, PredictionRecord, ProjectionStudy, Reliability } from './projection'
import { mean, num, pc, table } from './report'

export interface ProjectionCompetition { name: string; gender: string; games: number; projection: ProjectionStudy; slopes: Slopes; reliability: Reliability }

const FAMILIES: [string, string][] = [['Masculina', 'M'], ['Femenina', 'F']]
/** Below this many games where a condition happened, a family says nothing of its calibration. */
const MIN_MET = 30

const KEY_NAMES: Record<ResponseKey, string> = { efg: 'eFG', tov: 'pérdidas', orb: 'rebote ofensivo', ftr: 'tiros libres por tiro', oer: 'puntos / 100 pos.' }
const MEASURE_NAMES: Record<string, string> = { points: 'puntos', oer: 'puntos / 100 pos.', efg: 'eFG', tov: 'pérdidas', orb: 'rebote ofensivo', ftr: 'tiros libres por tiro' }
export const variableName = (id: VariableId): string => {
  if (id === 'game.possessions') return 'Posesiones'
  const [side, measure] = id.split('.')
  return `${side === 'own' ? 'Nuestro' : 'Rival'}: ${MEASURE_NAMES[measure]}`
}
/** A factor in percentage points, the rest as it is. */
const scaled = (id: VariableId | ResponseKey, x: number): number => (/(efg|tov|orb|ftr)$/.test(id) ? 100 * x : x)

const rmse = (rows: PredictionRecord[]): number => Math.sqrt(mean(rows.map(r => (scaled(r.target, r.predicted) - scaled(r.target, r.actual)) ** 2)))

function slopesSection(results: ProjectionCompetition[]): string {
  const row = (label: string, family: string, slopes: Slopes[]): (string | number)[] =>
    [label, family, ...RESPONSE_KEYS.map(k => num(mean(slopes.map(s => scaled(k, s[k]) * 0.1)), 2))]
  return [
    '### Cómo se mueve el juego con el ritmo',
    'Lo que cambia cada cosa de un equipo **por cada 10 % más de posesiones que las habituales de esos dos equipos** (la pendiente de la liga sobre la temporada completa; factores en puntos porcentuales, puntos por 100 posesiones en puntos).',
    table(['Competición', 'Familia', ...RESPONSE_KEYS.map(k => KEY_NAMES[k])], [
      ...results.map(r => row(r.name, r.gender, [r.slopes])),
      ...FAMILIES.filter(([, g]) => results.some(r => r.gender === g)).map(([label, g]) => row(`**${label}**`, g, results.filter(r => r.gender === g).map(r => r.slopes))),
    ]),
  ].join('\n\n')
}

function reliabilitySection(results: ProjectionCompetition[]): string {
  const cells = (rel: Reliability[]): string[] => RESPONSE_KEYS.map(k => `${num(mean(rel.map(r => r[k].attack)), 2)} / ${num(mean(rel.map(r => r[k].defence)), 2)}`)
  return [
    '### Si es propio de cada equipo',
    'La correlación, entre los equipos de una temporada, de la pendiente de cada uno con sus partidos impares y con sus partidos pares (lo que hace / lo que deja hacer). Cerca de 0: la pendiente de un equipo es ruido y la de la liga es lo que vale; cerca de 1: es un rasgo del equipo.',
    table(['Competición', ...RESPONSE_KEYS.map(k => KEY_NAMES[k])], [
      ...results.map(r => [r.name, ...cells([r.reliability])]),
      ...FAMILIES.filter(([, g]) => results.some(r => r.gender === g)).map(([label, g]) => [`**${label}**`, ...cells(results.filter(r => r.gender === g).map(r => r.reliability))]),
    ]),
  ].join('\n\n')
}

interface Calibration { n: number; met: number; predicted: number; actual: number; se: number; brier: number; brierHeadline: number }

function calibrationOf(rows: ConditionRecord[]): Calibration {
  const met = rows.filter(r => r.met)
  const actual = mean(met.map(r => r.y))
  return { n: rows.length, met: met.length, predicted: mean(met.map(r => r.pWin)), actual, se: Math.sqrt((actual * (1 - actual)) / met.length),
    brier: mean(met.map(r => brier(r.pWin, r.y))), brierHeadline: mean(met.map(r => brier(r.headline, r.y))) }
}

const calibrated = (c: Calibration): boolean => Math.abs(c.predicted - c.actual) <= 2 * c.se && c.brier <= c.brierHeadline

/** Whether the families with enough cases back the probability of a set of conditions: calibrated and no worse than the headline in each, and at least one of them. */
export function backed(rowsByFamily: ConditionRecord[][]): boolean {
  const judged = rowsByFamily.map(calibrationOf).filter(c => c.met >= MIN_MET)
  return judged.length > 0 && judged.every(calibrated)
}

const calibrationCells = (c: Calibration): (string | number)[] =>
  [c.n, c.met, pc(c.predicted), pc(c.actual), `±${pc(2 * c.se)}`, num(c.brier), num(c.brierHeadline)]

function conditionsSection(results: ProjectionCompetition[]): string {
  const of = (g: string): ConditionRecord[] => results.filter(r => r.gender === g).flatMap(r => r.projection.conditions)
  const all = results.flatMap(r => r.projection.conditions)
  const singles = (rows: ConditionRecord[], id: VariableId, layer: string) => rows.filter(r => r.conditions.length === 1 && r.conditions[0].variable === id && r.layer === layer)
  const head = ['Preguntas', 'Se cumplen', 'Prevista si se cumple', 'Real si se cumple', '± 2 errores típicos', 'Brier de la prevista', 'Brier del pronóstico']
  const byVariable = (['liga', 'equipo'] as const).flatMap(layer => VARIABLES.flatMap(v => FAMILIES.map(([label, g]) => {
    const rows = singles(of(g), v.id, layer)
    return rows.length ? [variableName(v.id), label, layer, ...calibrationCells(calibrationOf(rows))] : null
  }).filter((r): r is (string | number)[] => r !== null)))
  const verdicts = VARIABLES.map(v => [variableName(v.id), ...(['liga', 'equipo'] as const).map(layer => (backed(FAMILIES.map(([, g]) => singles(of(g), v.id, layer))) ? 'sí' : 'no'))])
  const byMass = [0.05, 0.1, 0.25, 0.5].map(target => {
    const rows = all.filter(r => r.conditions.length === 1 && r.layer === 'liga' && r.target === target)
    return [pc(target, 0), pc(mean(rows.map(r => r.mass))), ...calibrationCells(calibrationOf(rows))]
  })
  const pairs = (['liga', 'equipo'] as const).flatMap(layer => FAMILIES.map(([label, g]) => {
    const rows = of(g).filter(r => r.conditions.length === 2 && r.layer === layer)
    return rows.length ? [label, layer, ...calibrationCells(calibrationOf(rows))] : null
  }).filter((r): r is (string | number)[] => r !== null))
  return [
    '### Probabilidad con condiciones',
    'Cada variable se pregunta una vez por partido y lado, en una dirección y con el umbral donde empieza una parte de los escenarios (5, 10, 25 o 50 %), sorteadas con una semilla del partido; y tres parejas por partido y lado. ¿Lo cumplió el partido que se jugó?, ¿ganó el equipo? Cuando se cumple, la probabilidad prevista debería coincidir con la frecuencia real.',
    '#### Por variable', table(['Variable', 'Familia', 'Capa', ...head], byVariable),
    `#### Respaldo (el criterio de los objetivos del 11/11/2026: en cada familia con ${MIN_MET} o más casos, la prevista a dos errores típicos de la real y un Brier no peor que el del pronóstico)`,
    table(['Variable', 'Capa de liga', 'Capa de equipo'], verdicts),
    '#### Por parte de los escenarios (capa de liga, todas las variables)', table(['Umbral en el', 'Masa prevista (media)', ...head], byMass),
    '#### Dos condiciones a la vez', table(['Familia', 'Capa', ...head], pairs),
  ].join('\n\n')
}

function predictionsSection(results: ProjectionCompetition[]): string {
  const rows = results.flatMap(r => r.projection.predictions)
  const layers = [...new Set(rows.map(r => r.layer))]
  const givens = [...new Set(rows.map(r => r.given))]
  const body = givens.flatMap(given => VARIABLES.filter(v => v.id !== given).map(v => {
    const mine = rows.filter(r => r.given === given && r.target === v.id)
    return [variableName(given), variableName(v.id), ...layers.map(layer => num(rmse(mine.filter(r => r.layer === layer)), 2))]
  }))
  return [
    '### Prever el resto del partido',
    'Sabiendo una variable del partido que se jugó (sus posesiones, ±1, o los puntos de un lado, ±2), el error cuadrático medio al prever las demás (factores en puntos porcentuales) sin condicionar, con la capa de liga y con la de cada equipo (k = partidos de encogimiento hacia la liga). Menos es mejor.',
    table(['Sabiendo', 'Variable', ...layers.map(l => (l === 'ninguna' ? 'Sin condicionar' : l === 'liga' ? 'Capa de liga' : `Capa de ${l}`))], body),
  ].join('\n\n')
}

export function formatProjectionSection(results: ProjectionCompetition[]): string {
  return [
    '## Proyección multifactorial',
    table(['Competición', 'Familia', 'Partidos', 'Proyecciones', 'Sin escenarios suficientes'], results.map(r => [r.name, r.gender === 'F' ? 'femenina' : 'masculina', r.games, new Set(r.projection.conditions.map(c => `${c.k}|${c.court}`)).size, r.projection.skipped])),
    slopesSection(results), reliabilitySection(results), conditionsSection(results), predictionsSection(results),
  ].join('\n\n') + '\n'
}
