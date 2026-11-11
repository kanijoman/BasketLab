/** The matchup factor by factor (issue #849): what each team is expected to make against the other, the league average and who has the edge. */
import { useMemo } from 'react'
import type { ColumnDef } from '@tanstack/react-table'
import { FACTOR_NAMES, pct } from '@/forecast/copy'
import type { MatchupRow } from '@/forecast/matchup'
import DataTable from '@/components/ui/DataTable'
import ToneBadge from './ToneBadge'
import { signed } from './format'

export default function MatchupTable({ rows }: { rows: MatchupRow[] }) {
  const columns = useMemo<ColumnDef<MatchupRow, unknown>[]>(() => [
    { id: 'factor', header: 'Factor', size: 170, enableSorting: false, cell: ({ row }) => FACTOR_NAMES[row.original.factor] },
    { id: 'own', header: 'Nuestro equipo', enableSorting: false, cell: ({ row }) => pct(row.original.expectedOwn) },
    { id: 'rival', header: 'El rival', enableSorting: false, cell: ({ row }) => pct(row.original.expectedRival) },
    { id: 'league', header: 'Media de la liga', enableSorting: false, cell: ({ row }) => pct(row.original.league) },
    { id: 'edge', header: 'Ventaja', size: 190, enableSorting: false, cell: ({ row }) => {
      const { advantage, edge } = row.original
      return <ToneBadge tone={advantage === 'own' ? 'ok' : advantage === 'rival' ? 'bad' : 'neutral'}>{advantage === 'own' ? 'Nuestra' : advantage === 'rival' ? 'Del rival' : 'Igualado'} ({signed(edge)} por 100 posesiones)</ToneBadge>
    } },
  ], [])
  return (
    <section aria-label="Emparejamiento" className="space-y-2">
      <h2 className="text-lg font-semibold text-ink">Emparejamiento</h2>
      <p className="text-xs text-ink-muted">Lo que se espera que haga cada equipo contra el otro (lo que suele hacer más lo que el otro suele dejar) y lo que vale la diferencia, en puntos por 100 posesiones.</p>
      <DataTable columns={columns} data={rows} density="compact" ariaLabel="Emparejamiento por factor" />
    </section>
  )
}
