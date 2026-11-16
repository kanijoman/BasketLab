/**
 * One condition of the card «¿Y si…?» (#940): the variable (ours, the rival's or the game's), «menos de» / «más de» and the value as the page writes it (shares and free throws per 100), with
 * what is expected of this matchup as a hint. What is typed and is not a number is said so and does not change the question.
 */
import { useState } from 'react'
import { X } from 'lucide-react'
import { decimal, VARIABLE_NAMES } from '@/forecast/copy'
import { fromInput, parseNumber, toInput } from '@/forecast/projection/query'
import { VARIABLES, type Condition, type VariableId } from '@/forecast/projection/variables'
import { IconButton } from '@/components/ui/Button'
import { Field, Input, Select } from '@/components/ui/Field'
import SegmentedControl from '@/components/ui/SegmentedControl'

const GROUPS: [string, string][] = [['Nosotros', 'own.'], ['Rival', 'rival.'], ['Partido', 'game.']]
const OPS: { value: Condition['op']; label: string }[] = [{ value: 'lt', label: 'menos de' }, { value: 'gt', label: 'más de' }]

/** What the value is in: a share, free throws per 100 shots, or as it is. */
const unitOf = (id: VariableId): string => (/\.(efg|tov|orb)$/.test(id) ? ' (%)' : id.endsWith('.ftr') ? ' (por 100 tiros)' : '')

interface Props {
  condition: Condition
  /** Its place in the question, from 1. */
  n: number
  /** The value the page suggests for a variable (what is expected of this matchup), as the page writes it. */
  suggest: (id: VariableId) => number
  onChange: (c: Condition) => void
  onRemove: () => void
}

export default function ConditionRow({ condition, n, suggest, onChange, onRemove }: Props) {
  const [text, setText] = useState(() => decimal(toInput(condition)))
  const wrong = parseNumber(text) === null
  const type = (value: string) => {
    setText(value)
    const input = parseNumber(value)
    if (input !== null) onChange(fromInput(condition.variable, condition.op, input))
  }
  return (
    // on a phone the button to remove goes up next to the variable (it would be left alone on a line of its own); from 640 px, at the end of the row
    <div data-testid="condition" className="flex flex-wrap items-start gap-3">
      <Field label={`Condición ${n}`} className="order-1 min-w-[12rem] flex-1 sm:order-none">
        <Select value={condition.variable} onChange={e => { const id = e.target.value as VariableId; onChange(fromInput(id, condition.op, suggest(id))) }}>
          {GROUPS.map(([label, prefix]) => (
            <optgroup key={label} label={label}>
              {VARIABLES.filter(v => v.id.startsWith(prefix)).map(v => <option key={v.id} value={v.id}>{VARIABLE_NAMES[v.id]}</option>)}
            </optgroup>
          ))}
        </Select>
      </Field>
      <div className="order-3 flex flex-col gap-1 sm:order-none">
        <span className="text-xs font-medium text-ink-muted" aria-hidden="true">Cuándo</span>
        <SegmentedControl label={`Condición ${n}: menos de o más de`} options={OPS} value={condition.op} onChange={op => onChange({ ...condition, op })} />
      </div>
      <Field label={`Valor${unitOf(condition.variable)}`} hint={`Esperado: ${decimal(suggest(condition.variable))}`} error={wrong ? 'Escribe un número' : undefined} className="order-4 w-36 sm:order-none">
        <Input inputMode="decimal" value={text} onChange={e => type(e.target.value)} />
      </Field>
      <IconButton icon={X} label={`Quitar la condición ${n}`} onClick={onRemove} className="order-2 mt-5 sm:order-none" />
    </div>
  )
}
