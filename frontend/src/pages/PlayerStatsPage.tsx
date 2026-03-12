import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  useReactTable,
  type SortingState,
  type ColumnFiltersState,
} from '@tanstack/react-table'
import { getPlayerStats, type PlayerStat } from '@/api/client'

const col = createColumnHelper<PlayerStat>()

const columns = [
  col.accessor('player_name', { header: 'Jugador', size: 180 }),
  col.accessor('team_name',   { header: 'Equipo',   size: 140 }),
  col.accessor('games_played',       { header: 'PJ',   size: 50 }),
  col.accessor('minutes_per_game',   { header: 'MIN',  size: 60, cell: i => i.getValue()?.toFixed(1) }),
  col.accessor('points_per_game',    { header: 'PTS',  size: 60, cell: i => i.getValue()?.toFixed(1) }),
  col.accessor('rebounds_per_game',  { header: 'REB',  size: 60, cell: i => i.getValue()?.toFixed(1) }),
  col.accessor('assists_per_game',   { header: 'AST',  size: 60, cell: i => i.getValue()?.toFixed(1) }),
]

/**
 * Per-player statistics table with team name filter.
 */
export default function PlayerStatsPage() {
  const { collection } = useParams<{ collection: string }>()
  const [stats, setStats] = useState<PlayerStat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sorting, setSorting] = useState<SortingState>([{ id: 'points_per_game', desc: true }])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [teamFilter, setTeamFilter] = useState('')

  useEffect(() => {
    if (!collection) return
    setLoading(true)
    getPlayerStats(collection)
      .then(setStats)
      .catch(err => setError(err instanceof Error ? err.message : 'Error'))
      .finally(() => setLoading(false))
  }, [collection])

  // Sync teamFilter input → TanStack column filter
  useEffect(() => {
    setColumnFilters(teamFilter ? [{ id: 'team_name', value: teamFilter }] : [])
  }, [teamFilter])

  const table = useReactTable({
    data: stats,
    columns,
    state: { sorting, columnFilters },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    filterFns: {
      // Case-insensitive team name filter
      auto: (row, columnId, value: string) =>
        String(row.getValue(columnId)).toLowerCase().includes(value.toLowerCase()),
    },
  })

  if (loading) return <p className="text-gray-500 mt-8 text-center">Cargando estadísticas de jugadores…</p>
  if (error) return <p className="text-red-600 mt-8 text-center">{error}</p>

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-court-950">Estadísticas de Jugadores</h1>
          <p className="text-gray-500 text-sm mt-1">{collection}</p>
        </div>
        <input
          type="search"
          placeholder="Filtrar por equipo…"
          value={teamFilter}
          onChange={e => setTeamFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 w-48"
        />
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-court-950 text-white">
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id}>
                {hg.headers.map(header => (
                  <th
                    key={header.id}
                    onClick={header.column.getToggleSortingHandler()}
                    className="px-3 py-2 text-left font-semibold cursor-pointer select-none whitespace-nowrap hover:bg-court-800 transition-colors"
                    style={{ width: header.getSize() }}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    {header.column.getIsSorted() === 'asc' && ' ↑'}
                    {header.column.getIsSorted() === 'desc' && ' ↓'}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-gray-100">
            {table.getRowModel().rows.map((row, i) => (
              <tr
                key={row.id}
                className={i % 2 === 0 ? 'bg-white hover:bg-orange-50' : 'bg-gray-50 hover:bg-orange-50 transition-colors'}
              >
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="px-3 py-2 whitespace-nowrap">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-gray-400 text-xs mt-2">
        {table.getRowModel().rows.length} jugadores · Haz clic en las columnas para ordenar
      </p>
    </div>
  )
}
