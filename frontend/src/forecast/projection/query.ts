// The conditions of the card «¿Y si…?» (#940) as the page writes them and in the address, so that a preview with its questions can be shared and reloaded:
// `?si=own.points.gt.70_rival.efg.lt.40` (variable, «more than» `gt` or «less than» `lt`, and the value as the page writes it; `_` between conditions: only letters, digits, `.` and `_`, which
// an address keeps as they are). The page writes the shares and the free throws per 100 shots (40 is 40 %) and the rest as they are. What cannot be read is left out, never an error.
import type { Projection } from './build'
import { project } from './project'
import { VARIABLES, type Condition, type VariableId } from './variables'

/** The most conditions a question has. */
export const MAX_CONDITIONS = 3

const IDS = new Set<string>(VARIABLES.map(v => v.id))
const PER_100 = /\.(efg|tov|orb|ftr)$/

/** What a value is multiplied by to be written: the shares and the free throws per 100 shots, 100; the rest, 1. */
const scaleOf = (id: VariableId): number => (PER_100.test(id) ? 100 : 1)

export const toInput = (c: Condition): number => c.value * scaleOf(c.variable)
export const fromInput = (variable: VariableId, op: Condition['op'], input: number): Condition => ({ variable, op, value: input / scaleOf(variable) })

/** A number as it is typed (`40,5`, `18.25`, ` 70 `); null when it is not one, or it is negative. */
export function parseNumber(text: string): number | null {
  const t = text.trim()
  return /^\d+([.,]\d+)?$/.test(t) ? Number(t.replace(',', '.')) : null
}

/** The value written with up to four decimals and the point (an address does not keep the comma as it is). */
const written = (x: number): string => String(Math.round(x * 1e4) / 1e4)

export const conditionsParam = (conditions: Condition[]): string => conditions.map(c => `${c.variable}.${c.op}.${written(toInput(c))}`).join('_')

export function parseConditions(text: string | null): Condition[] {
  const read = (part: string): Condition | null => {
    const [group, measure, op, ...rest] = part.split('.')
    const variable = `${group}.${measure}`
    const input = parseNumber(rest.join('.'))
    return IDS.has(variable) && (op === 'gt' || op === 'lt') && input !== null ? fromInput(variable as VariableId, op, input) : null
  }
  return (text ?? '').split('_').map(read).filter((c): c is Condition => c !== null).slice(0, MAX_CONDITIONS)
}

/** What the page suggests for a variable: what is expected of this matchup, the points and the possessions whole and the rest to one decimal (as the page writes it). */
export function suggestedInput(p: Projection, id: VariableId): number {
  const expected = project(p, []).profile.find(r => r.variable === id)!.expected * scaleOf(id)
  return id.endsWith('.points') || id === 'game.possessions' ? Math.round(expected) : Math.round(expected * 10) / 10
}

/** The question the card starts with when the address has none: our points over what is expected. */
export const defaultConditions = (p: Projection): Condition[] => [fromInput('own.points', 'gt', suggestedInput(p, 'own.points'))]
