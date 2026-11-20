// What a player would be expected to do in another competition (#891, E4): ONE estimate per player, always a RANGE (the 80 % interval of his percentile in the competition he is translated to), never a single
// figure. Which seasons it is built from (the last one, or the average of the last two) is said but never chosen by the reader. When the model did not hold its validation (`usable` false) the range is shown
// as indicative. A player whose latest competition is not in the graph (FBCYL, the formation) is told so. The numbers are those of `equivalence.ts`, which Python pins with parity vectors.
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Badge from '@/components/ui/Badge'
import Card from '@/components/ui/Card'
import { Field, Select } from '@/components/ui/Field'
import Spinner from '@/components/ui/Spinner'
import { loadEquivalences, type TalentCompetitionEntry } from './data'
import { estimateFromDocument, historyOf, origin, targetsOf, type EquivalenceDocument, type EstimateOrigin } from './equivalence'
import { RADAR_AXES } from './player'
import type { SearchRow } from './search'

const name = (node: string) => node.split('|')[2]

function Band({ lo, mean, hi }: { lo: number; mean: number; hi: number }) {
  const clamp = (v: number) => Math.min(100, Math.max(0, v))
  return (
    <div aria-hidden="true" className="relative h-2 w-full min-w-24 rounded-pill bg-line/50">
      <div className="absolute inset-y-0 rounded-pill bg-accent/30" style={{ left: `${clamp(lo)}%`, width: `${Math.max(clamp(hi) - clamp(lo), 1)}%` }} />
      <div className="absolute -top-0.5 h-3 w-0.5 bg-ink" style={{ left: `${clamp(mean)}%` }} />
    </div>
  )
}

/** The estimate of a player from his observations (`history`) against the document; the reader picks only the competition. */
export function EquivalenceView({ doc, history }: { doc: EquivalenceDocument; history: EstimateOrigin[] }) {
  const start = useMemo(() => origin(history), [history])
  const targets = useMemo(() => (start ? targetsOf(doc, start.last.node) : []), [doc, start])
  const [picked, setPicked] = useState<string | null>(null)
  if (!start) return <p className="text-sm text-ink-muted">Sin traducción: no tiene una temporada sénior de FEB con minutos suficientes en el grafo de equivalencias (la formación y FBCYL todavía no están en él).</p>
  if (!targets.length) return <p className="text-sm text-ink-muted">Sin traducción: {name(start.last.node)} no está conectada con otras competiciones del grafo.</p>
  const to = picked && targets.includes(picked) ? picked : targets[0]
  const estimate = estimateFromDocument(doc, history, to) ?? []
  return (
    <div className="space-y-3">
      <Field label="Si jugara en">
        <Select value={to} onChange={e => setPicked(e.target.value)} options={targets.map(t => ({ value: t, label: name(t) }))} />
      </Field>
      <p className="text-xs text-ink-muted">
        Percentil que se esperaría en {name(to)} a partir de {start.seasons === 2 ? 'la media de sus dos últimas temporadas' : 'su última temporada'} en {name(start.last.node)}. Es un margen del 80 %: de cada diez jugadores así, unos ocho quedarían dentro; no es una promesa.
      </p>
      {!doc.usable && <Badge tone="warn" title="La validación del modelo no cumplió el criterio de publicación">Orientativo</Badge>}
      <table aria-label="Margen esperado por eje" className="w-full border-collapse text-sm">
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

/** The card of the profile: loads the equivalences of the publication and the history of the player from his rows. */
export default function PlayerEquivalence({ rows, entries }: { rows: SearchRow[]; entries: TalentCompetitionEntry[] }) {
  const equivalences = useQuery({ queryKey: ['talent-equivalences'], queryFn: loadEquivalences, retry: false })
  const history = useMemo(() => {
    const byKey = new Map(entries.map(e => [e.key, e]))
    return historyOf(rows.flatMap(r => { const entry = byKey.get(r.comp_key); return entry ? [{ entry, row: r }] : [] }))
  }, [rows, entries])
  return (
    <Card id="equivalencias" title="En otra competición">
      {equivalences.isLoading && <Spinner size="sm" label="Cargando las equivalencias" />}
      {equivalences.isError && <p className="text-sm text-ink-muted">No se han podido abrir las equivalencias entre competiciones.</p>}
      {equivalences.isSuccess && !equivalences.data && <p className="text-sm text-ink-muted">Esta publicación todavía no tiene equivalencias entre competiciones.</p>}
      {equivalences.data && <EquivalenceView doc={equivalences.data} history={history} />}
    </Card>
  )
}
