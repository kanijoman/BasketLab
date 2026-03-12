import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { getTeamStats, type TeamStat } from '@/api/client'

const col = createColumnHelper<TeamStat>()

const columns = [
  col.accessor('team_name', { header: 'Equipo', size: 180 }),
  col.accessor('games_played', { header: 'PJ', size: 55 }),
  col.accessor('points_per_game', {
    header: 'PPP',
    size: 65,
    cell: info => info.getValue()?.toFixed(1),
  }),
  col.accessor('field_goals_2_pct', {
    header: 'T2%',
    size: 65,
    cell: info => `${(((info.getValue() as number) ?? 0) * 100).toFixed(1)}%`,
  }),
  col.accessor('field_goals_3_pct', {
    header: 'T3%',
    size: 65,
    cell: info => `${(((info.getValue() as number) ?? 0) * 100).toFixed(1)}%`,
  }),
  col.accessor('free_throw_pct', {
    header: 'TL%',
    size: 65,
    cell: info => `${(((info.getValue() as number) ?? 0) * 100).toFixed(1)}%`,
  }),
  col.accessor('rebounds_per_game', {
    header: 'RPP',
    size: 60,
    cell: info => info.getValue()?.toFixed(1),
  }),
  col.accessor('assists_per_game', {
    header: 'APP',
    size: 60,
    cell: info => info.getValue()?.toFixed(1),
  }),
  col.accessor('steals_per_game', {
    header: 'ROBPP',
    size: 70,
    cell: info => info.getValue()?.toFixed(1),
  }),
  col.accessor('turnovers_per_game', {
    header: 'PERPP',
    size: 70,
    cell: info => info.getValue()?.toFixed(1),
  }),
]

/**
 * Team statistics table for one collection (season + group).
 * Supports column-click sorting via TanStack Table.
 */
export default function TeamStatsPage() {
  const { collection } = useParams<{ collection: string }>()
  const [stats, setStats] = useState<TeamStat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sorting, setSorting] = useState<SortingState>([])

  useEffect(() => {
    if (!collection) return
    setLoading(true)
    getTeamStats(collection)
      .then(data => setStats(data.team_stats))
      .catch(err => setError(err instanceof Error ? err.message : 'Error'))
      .finally(() => setLoading(false))
  }, [collection])

  const table = useReactTable({
    data: stats,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  if (loading) return <p className="text-gray-500 mt-8 text-center">Cargando estadísticas…</p>
  if (error) return <p className="text-red-600 mt-8 text-center">{error}</p>

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-court-950">Estadísticas de Equipo</h1>
          <p className="text-gray-500 text-sm mt-1">{collection}</p>
        </div>
        <div className="flex gap-2">
          <Link
            to={`/players/${collection}`}
            className="bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition-colors"
          >
            Jugadores →
          </Link>
          <Link
            to={`/lineups/${collection}`}
            className="bg-gray-800 hover:bg-gray-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition-colors"
          >
            Quintetos →
          </Link>
        </div>
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
                className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50 hover:bg-orange-50 transition-colors'}
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
        {stats.length} equipos · Haz clic en las columnas para ordenar
      </p>
    </div>
  )
}
