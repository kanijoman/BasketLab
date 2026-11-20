// What a player of the formation would be in the senior game IF he gets there (#893, E3c): ONE estimate, always a RANGE (the 80 % interval of his percentile in the senior competition chosen), never a figure, and
// always said as CONDITIONAL: the index is made of those who made it, so it is not the chance of making it. Without the index in the publication, or for a player who is not of a group it speaks of, the card is not
// there. When the validation did not hold (`usable` false) it is shown as indicative. The numbers are those of `formation.ts`, which Python pins with parity vectors.
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Badge from '@/components/ui/Badge'
import Card from '@/components/ui/Card'
import { Field, Select } from '@/components/ui/Field'
import { loadEquivalences, loadFormation, type TalentCompetitionEntry } from './data'
import type { EquivalenceDocument } from './equivalence'
import { estimateFormation, formationOf, type FormationDocument, type FormationObs } from './formation'
import { Band } from './PlayerEquivalence'
import { RADAR_AXES } from './player'
import type { SearchRow } from './search'

const name = (node: string) => node.split('|')[2]

/** The estimate of a player of the formation from his observations against the two documents; the reader picks only the senior competition. */
export function FormationView({ doc, equivalences, history }: { doc: FormationDocument; equivalences: EquivalenceDocument; history: FormationObs[] }) {
  const last = useMemo(() => (history.length ? history.reduce((b, o) => (o.season > b.season ? o : b)) : null), [history])
  const targets = useMemo(() => (last ? (equivalences.sexes[last.sex]?.nodes ?? []) : []), [last, equivalences])
  const [picked, setPicked] = useState<string | null>(null)
  if (!last || !doc.groups.includes(last.group) || !targets.length) return null
  const to = picked && targets.includes(picked) ? picked : targets[0]
  const estimate = estimateFormation(doc, equivalences, history, to) ?? []
  return (
    <div className="space-y-3">
      <Field label="Si llega al sénior, en">
        <Select value={to} onChange={e => setPicked(e.target.value)} options={targets.map(t => ({ value: t, label: name(t) }))} />
      </Field>
      <p className="text-xs text-ink-muted">
        Percentil que se esperaría en {name(to)} a partir de su temporada en {last.group}. Es lo esperable de los jugadores que sí llegan al juego sénior con minutos: <strong className="font-medium text-ink">no es la probabilidad de llegar</strong>.
        Margen del 80 %: de cada diez jugadores así que llegan, unos ocho quedarían dentro.
      </p>
      {!doc.usable && <Badge tone="warn" title="La validación del índice no cumplió el criterio de publicación">Orientativo</Badge>}
      <table aria-label="Margen esperado en el sénior por eje" className="w-full border-collapse text-sm">
        <thead><tr className="text-left text-xs text-ink-muted"><th scope="col" className="py-1 pr-2 font-medium">Eje</th><th scope="col" className="py-1 pr-2 font-medium">Margen</th><th scope="col" className="py-1 font-medium"><span className="sr-only">Gráfico</span></th></tr></thead>
        <tbody>
          {estimate.map((e, i) => (
            <tr key={RADAR_AXES[i].key} className="border-t border-line/50">
              <th scope="row" className="py-1.5 pr-2 text-left font-normal text-ink-muted">{RADAR_AXES[i].label}</th>
              <td className="py-1.5 pr-2 tabular-nums text-ink">{Math.round(e.pct_lo)}–{Math.round(e.pct_hi)} <span className="text-ink-muted">(centro {Math.round(e.pct_mean)})</span></td>
              <td className="py-1.5"><Band lo={e.pct_lo} mean={e.pct_mean} hi={e.pct_hi} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** The card of the profile: only for a player who has formation of FEB in a group the index speaks of. */
export default function PlayerFormation({ rows, entries }: { rows: SearchRow[]; entries: TalentCompetitionEntry[] }) {
  const formation = useQuery({ queryKey: ['talent-formation'], queryFn: loadFormation, retry: false })
  const equivalences = useQuery({ queryKey: ['talent-equivalences'], queryFn: loadEquivalences, retry: false })
  const history = useMemo(() => {
    const byKey = new Map(entries.map(e => [e.key, e]))
    return formationOf(rows.flatMap(r => { const entry = byKey.get(r.comp_key); return entry ? [{ entry, row: r }] : [] }))
  }, [rows, entries])
  if (!formation.data || !equivalences.data || !history.length) return null
  const view = <FormationView doc={formation.data} equivalences={equivalences.data} history={history} />
  return <Card id="formacion" title="Si llega al sénior">{view}</Card>
}
