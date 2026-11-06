/** The receivers of a team: every player who scored, sortable by any column, a click opens his detail (issue #773). */
import { useMemo } from 'react'
import type { ColumnDef } from '@tanstack/react-table'
import type { Receiver } from '@/api/assistConnections'
import DataTable from '@/components/ui/DataTable'
import { pct } from './format'

interface Props {
  receivers: Receiver[]
  selectedId: string | null
  onSelect: (playerId: string) => void
}

export default function ReceiverTable({ receivers, selectedId, onSelect }: Props) {
  const columns = useMemo<ColumnDef<Receiver, unknown>[]>(() => [
    { id: 'name', accessorKey: 'name', header: 'Jugador', size: 170,
      cell: ({ row }) => <span data-testid="receiver-name" className={row.original.player_id === selectedId ? 'font-semibold text-accent-text' : ''}>{row.original.name}</span> },
    { id: 'received', accessorKey: 'received', header: 'Asist. recibidas', cell: ({ row }) => row.original.received },
    { id: 'share_pct', accessorKey: 'share_pct', header: '% de las asist. del equipo', cell: ({ row }) => pct(row.original.share_pct) },
    { id: 'fgm', accessorKey: 'fgm', header: 'Canastas', cell: ({ row }) => row.original.fgm },
    { id: 'assisted_pct', accessorKey: 'assisted_pct', header: '% canastas asistidas', cell: ({ row }) => pct(row.original.assisted_pct) },
    { id: 'assisted_points_pct', accessorKey: 'assisted_points_pct', header: '% puntos asistidos', cell: ({ row }) => pct(row.original.assisted_points_pct) },
  ], [selectedId])
  return <DataTable columns={columns} data={receivers} onRowClick={row => onSelect(row.original.player_id)} ariaLabel="Tabla de receptores" density="compact" />
}
