/** The passers of a team: who gives the assists and who they usually find (issue #773). */
import { useMemo } from 'react'
import type { ColumnDef } from '@tanstack/react-table'
import type { Passer } from '@/api/assistConnections'
import DataTable from '@/components/ui/DataTable'
import { pct } from './format'

const TOP = 3

export default function PassersTable({ passers, onSelect }: { passers: Passer[]; onSelect: (playerId: string) => void }) {
  const columns = useMemo<ColumnDef<Passer, unknown>[]>(() => [
    { id: 'name', accessorKey: 'name', header: 'Jugador', size: 170, cell: ({ row }) => row.original.name },
    { id: 'assists', accessorKey: 'assists', header: 'Asistencias', cell: ({ row }) => row.original.assists },
    { id: 'share_pct', accessorKey: 'share_pct', header: '% de las asist. del equipo', cell: ({ row }) => pct(row.original.share_pct) },
    { id: 'to', header: 'A quién suele encontrar', enableSorting: false, size: 260,
      cell: ({ row }) => row.original.to.slice(0, TOP).map(t => `${t.name} (${t.count})`).join(', ') },
  ], [])
  return (
    <section aria-label="Pasadores" className="space-y-2">
      <h2 className="text-lg font-semibold text-ink">Pasadores</h2>
      <DataTable columns={columns} data={passers} onRowClick={row => onSelect(row.original.player_id)} ariaLabel="Tabla de quien da las asistencias" density="compact" emptyMessage="Ningún pase de asistencia se ha podido enlazar a una canasta." />
    </section>
  )
}
