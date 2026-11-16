/**
 * The card «¿Y si…? Probabilidad con condiciones» (#940): up to three conditions on the game (ours, the rival's or the game's), and the answer of the projection of the match for the games like
 * this one where all of them hold: how often, how often we win then (only when the evaluation backs it and they are at least 5 of every 100), how the season went for both teams in that
 * situation, what those games look like against the usual and where the points come from. Everything in sight, no folding, so the PDF takes it whole. Conditional, never a promise.
 */
import { useMemo } from 'react'
import { Plus } from 'lucide-react'
import { conditionsTitle, pointsLine, profileValue, projectionLines, recordLines, VARIABLE_NAMES } from '@/forecast/copy'
import type { Projection } from '@/forecast/projection/build'
import { movers, type ProjectionResult } from '@/forecast/projection/project'
import { fromInput, MAX_CONDITIONS, suggestedInput } from '@/forecast/projection/query'
import { VARIABLES, type Condition, type VariableId } from '@/forecast/projection/variables'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import { cn } from '@/lib/utils'
import ConditionRow from './ConditionRow'

/** The variable a new condition starts on: the first of these not asked yet, then the rest. */
const NEXT: VariableId[] = ['own.points', 'rival.points', 'own.efg', 'rival.efg', ...VARIABLES.map(v => v.id)]

/**
 * What those games look like against the usual, every variable. A plain table and not a `DataTable`: three short columns that read as a table on a phone too (a `DataTable` turns every row
 * into a card there, thirteen of them), with nothing to sort or search; the same shape as the heat map of the simulation.
 */
function Profile({ result }: { result: ProjectionResult }) {
  const moved = useMemo(() => new Set(movers(result)), [result])
  const cell = 'px-2 py-1.5 text-right tabular-nums'
  return (
    <div role="region" tabIndex={0} aria-label="Cómo son esos partidos, tabla" className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">Cómo son esos partidos</caption>
        <thead>
          <tr className="text-xs text-ink-muted">
            <th scope="col" className="px-2 py-1.5 text-left font-medium">Cómo son esos partidos</th>
            <th scope="col" className={cn(cell, 'font-medium')}>Lo habitual</th>
            <th scope="col" className={cn(cell, 'font-medium')}>En esos partidos</th>
          </tr>
        </thead>
        <tbody>
          {result.profile.map(({ variable, expected, given }) => {
            const up = given > expected
            return (
              <tr key={variable} className="border-t border-line/40">
                <th scope="row" className="px-2 py-1.5 text-left font-normal text-ink">{VARIABLE_NAMES[variable]}</th>
                <td className={cn(cell, 'text-ink-muted')}>{profileValue(variable, expected)}</td>
                <td className={cn(cell, 'whitespace-nowrap text-ink')}>
                  {profileValue(variable, given)}
                  {moved.has(variable) && <><span aria-hidden="true" className="ml-1 text-accent-text">{up ? '▲' : '▼'}</span><span className="sr-only">{up ? ' (sube: de lo que más cambia)' : ' (baja: de lo que más cambia)'}</span></>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Answer({ result, headline, rivalName }: { result: ProjectionResult; headline: number; rivalName: string }) {
  const lines = projectionLines(result, headline)
  const records = recordLines(result, rivalName)
  return (
    <Card title={conditionsTitle(result.conditions)} actions={lines.badge && <Badge tone="accent">{lines.badge}</Badge>}>
      <div className="space-y-1 text-sm">
        <p className="text-ink">{lines.summary}</p>
        {lines.caveat && <p className="text-ink-muted">{lines.caveat}</p>}
        <p className="text-ink-muted">{records.own}</p>
        <p className="text-ink-muted">{records.rival}</p>
      </div>
      {result.mass > 0 && (
        <div className="mt-3 space-y-2">
          <Profile result={result} />
          <p className="text-xs text-ink-muted">▲ ▼ marcan lo que más cambia en esos partidos, sin contar lo que se ha elegido.</p>
          <p className="text-sm text-ink-muted">{pointsLine('own', result.points.own)}</p>
          <p className="text-sm text-ink-muted">{pointsLine('rival', result.points.rival)}</p>
        </div>
      )}
    </Card>
  )
}

interface Props {
  projection: Projection
  conditions: Condition[]
  /** The answer of the projection to `conditions` (none without conditions). */
  result: ProjectionResult | null
  onChange: (conditions: Condition[]) => void
  headline: number
  rivalName: string
}

export default function ProjectionCard({ projection, conditions, result, onChange, headline, rivalName }: Props) {
  const suggest = useMemo(() => {
    const cache = new Map<VariableId, number>()
    return (id: VariableId): number => { if (!cache.has(id)) cache.set(id, suggestedInput(projection, id)); return cache.get(id)! }
  }, [projection])
  const add = () => {
    const id = NEXT.find(v => !conditions.some(c => c.variable === v))!
    onChange([...conditions, fromInput(id, 'gt', suggest(id))])
  }
  return (
    <section aria-label="¿Y si…? Probabilidad con condiciones" className="space-y-3">
      <h2 className="text-lg font-semibold text-ink">¿Y si…? Probabilidad con condiciones</h2>
      <p className="text-sm text-ink-muted">
        Elige cómo va el partido: cómo son los partidos así y cuántos ganamos. Describe lo que pasa en esos partidos: no asegura que conseguirlo dé la victoria.
      </p>
      <div className="card space-y-3 p-4">
        {conditions.map((c, i) => (
          <ConditionRow key={`${i}-${c.variable}`} condition={c} n={i + 1} suggest={suggest}
            onChange={next => onChange(conditions.map((x, j) => (j === i ? next : x)))} onRemove={() => onChange(conditions.filter((_, j) => j !== i))} />
        ))}
        {conditions.length < MAX_CONDITIONS && <Button variant="secondary" size="sm" icon={Plus} onClick={add}>Añadir condición</Button>}
      </div>
      {result ? <Answer result={result} headline={headline} rivalName={rivalName} /> : <p className="text-sm text-ink-muted">Añade una condición para ver cómo son esos partidos y cuántos ganamos.</p>}
    </section>
  )
}
