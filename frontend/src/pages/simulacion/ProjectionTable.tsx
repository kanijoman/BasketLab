/** The table of the league (issue #850): the position now, the record, what the simulation expects of every team (wins, average position, chance of being first) and of each cut line. */
import { useMemo } from 'react'
import type { ColumnDef } from '@tanstack/react-table'
import { pct } from '@/forecast/copy'
import type { Cut } from '@/forecast/decisive'
import DataTable from '@/components/ui/DataTable'
import TeamCell, { teamColumn } from '@/components/ui/TeamCell'
import { cutLabel, type LeagueRow } from './rows'

const one = (x: number): string => x.toFixed(1).replace('.', ',')

export default function ProjectionTable({ rows, cuts, ownTeam }: { rows: LeagueRow[]; cuts: Cut[]; ownTeam: string | null }) {
  const columns = useMemo<ColumnDef<LeagueRow, unknown>[]>(() => [
    { id: 'position', accessorKey: 'position', header: 'Pos.', size: 60, cell: ({ row }) => row.original.position },
    {
      ...teamColumn(),
      cell: ({ row }) => (
        <span className="flex items-center gap-2">
          <TeamCell name={row.original.team_name} teamId={row.original.team_id} />
          {row.original.team_id === ownTeam && <span className="text-xs font-medium text-accent-text">tu equipo</span>}
        </span>
      ),
    },
    { id: 'played', accessorKey: 'played', header: 'PJ', size: 56, cell: ({ row }) => row.original.played },
    { id: 'record', accessorKey: 'record', header: 'G-P', size: 70, enableSorting: false, cell: ({ row }) => row.original.record },
    { id: 'diff', accessorKey: 'diff', header: 'Dif.', size: 64, cell: ({ row }) => (row.original.diff > 0 ? `+${row.original.diff}` : row.original.diff) },
    { id: 'expectedWins', accessorKey: 'expectedWins', header: 'Victorias esperadas', size: 120, cell: ({ row }) => one(row.original.expectedWins) },
    { id: 'meanPosition', accessorKey: 'meanPosition', header: 'Puesto medio', size: 100, cell: ({ row }) => one(row.original.meanPosition) },
    { id: 'pFirst', accessorKey: 'pFirst', header: 'Ser 1.º', size: 80, cell: ({ row }) => pct(row.original.pFirst, 0) },
    ...cuts.map((cut, i): ColumnDef<LeagueRow, unknown> => ({ id: `cut${i}`, header: cutLabel(cut), size: 130, accessorFn: row => row.cuts[i], cell: ({ row }) => pct(row.original.cuts[i], 0) })),
  ], [cuts, ownTeam])
  return <DataTable columns={columns} data={rows} density="compact" ariaLabel="Clasificación proyectada" exportOptions={{ filename: 'simulacion-liga' }} />
}
