/**
 * The cut lines of the reader (issue #850): «the first 4», «the last 2». The rules of promotion, play-off and relegation change with the competition and the season, so the page does not model
 * them: whoever reads it draws the lines that matter to them and the table says the chance of each team being inside. At most four, all inside the table, none repeated.
 */
import { useState } from 'react'
import { X } from 'lucide-react'
import type { Cut } from '@/forecast/decisive'
import Button from '@/components/ui/Button'
import { Field, Input, Select } from '@/components/ui/Field'

export const MAX_CUTS = 4

export default function CutLines({ cuts, teams, onChange }: { cuts: Cut[]; teams: number; onChange: (cuts: Cut[]) => void }) {
  const [kind, setKind] = useState<Cut['kind']>('top')
  const [n, setN] = useState('')
  const [error, setError] = useState<string | null>(null)

  const add = () => {
    const value = Number(n)
    if (n.trim() === '' || !Number.isInteger(value) || value < 1 || value > teams - 1) return setError(`Escribe un número de equipos entre 1 y ${teams - 1}.`)
    if (cuts.some(c => c.kind === kind && c.n === value)) return setError(null)
    if (cuts.length >= MAX_CUTS) return setError('Como mucho cuatro líneas.')
    setError(null)
    onChange([...cuts, { kind, n: value }])
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Línea de corte">
          <Select aria-label="Tipo de línea" value={kind} onChange={e => setKind(e.target.value as Cut['kind'])}>
            <option value="top">Primeros</option>
            <option value="bottom">Últimos</option>
          </Select>
        </Field>
        <Field label="Equipos">
          <Input aria-label="Número de equipos" type="number" min={1} max={teams - 1} value={n} onChange={e => setN(e.target.value)} className="w-24" />
        </Field>
        <Button variant="secondary" onClick={add}>Añadir línea</Button>
      </div>
      {error && <p role="alert" className="text-sm text-bad">{error}</p>}
      {cuts.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Líneas de corte">
          {cuts.map(c => {
            const text = `${c.kind === 'top' ? 'Primeros' : 'Últimos'} ${c.n}`
            return (
              <li key={`${c.kind}-${c.n}`} className="flex items-center gap-1 rounded-pill border border-line px-2.5 py-1 text-sm text-ink">
                {text}
                <Button variant="ghost" size="sm" aria-label={`Quitar la línea ${text}`} onClick={() => onChange(cuts.filter(x => x !== c))} className="!p-0.5"><X className="h-3.5 w-3.5" aria-hidden="true" /></Button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
