import { useState, FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { getLineupAnalysis, getTeamStats, type LineupRow } from '@/api/client'
import { useEffect } from 'react'
import { tippedHeader } from '@/components/ui/Tooltip'

const col = createColumnHelper<LineupRow>()

const columns = [
  col.accessor(
    row => (row.players as string[]).join(' · '),
    { id: 'players', header: 'Quinteto', size: 340 },
  ),
  col.accessor('minutes', {
    header: tippedHeader('MIN'),
    size: 65,
    cell: i => (i.getValue() as number)?.toFixed(1),
  }),
  col.accessor('points_for', { header: tippedHeader('PF'), size: 55 }),
  col.accessor('points_against', { header: tippedHeader('PC'), size: 55 }),
  col.accessor('plus_minus', {
    header: tippedHeader('+/-'),
    size: 60,
    cell: i => {
      const v = i.getValue() as number
      return (
        <span className={v > 0 ? 'text-green-600 font-semibold' : v < 0 ? 'text-red-600 font-semibold' : ''}>
          {v > 0 ? `+${v}` : v}
        </span>
      )
    },
  }),
  col.accessor('net_rating', {
    header: tippedHeader('Net Rtg'),
    size: 70,
    cell: i => {
      const v = i.getValue() as number
      return (
        <span className={v > 0 ? 'text-green-600 font-semibold' : v < 0 ? 'text-red-600 font-semibold' : ''}>
          {v?.toFixed(1)}
        </span>
      )
    },
  }),
]

/**
 * Lineup analysis page — select a team and run the combination analysis.
 */
export default function LineupsPage() {
  const { collection } = useParams<{ collection: string }>()
  const [teams, setTeams] = useState<string[]>([])
  const [selectedTeam, setSelectedTeam] = useState('')
  const [lineups, setLineups] = useState<LineupRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sorting, setSorting] = useState<SortingState>([{ id: 'net_rating', desc: true }])
  const [size, setSize] = useState(5)

  // Fetch team list once collection is known
  useEffect(() => {
    if (!collection) return
    getTeamStats(collection)
      .then(data => {
        const names = data.team_stats.map(t => t.team_name).sort()
        setTeams(names)
        if (names.length > 0) setSelectedTeam(names[0])
      })
      .catch(() => setTeams([]))
  }, [collection])

  async function handleAnalyze(e: FormEvent) {
    e.preventDefault()
    if (!collection || !selectedTeam) return
    setError(null)
    setLoading(true)
    try {
      const rows = await getLineupAnalysis(collection, selectedTeam, selectedTeam, size)
      setLineups(rows)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error')
    } finally {
      setLoading(false)
    }
  }

  const table = useReactTable({
    data: lineups,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div>
      <h1 className="text-2xl font-bold text-court-950 mb-4">Análisis de Quintetos</h1>
      <p className="text-gray-500 text-sm mb-6">{collection}</p>

      {/* Controls */}
      <form onSubmit={handleAnalyze} className="flex flex-wrap gap-4 items-end mb-6">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Equipo</label>
          <select
            value={selectedTeam}
            onChange={e => setSelectedTeam(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {teams.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Jugadores por quinteto</label>
          <select
            value={size}
            onChange={e => setSize(Number(e.target.value))}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {[2, 3, 4, 5].map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>

        <button
          type="submit"
          disabled={loading || !selectedTeam}
          className="bg-primary-600 hover:bg-primary-700 disabled:opacity-60 text-white text-sm font-medium rounded-lg px-5 py-1.5 transition-colors"
        >
          {loading ? 'Analizando…' : 'Analizar'}
        </button>
      </form>

      {error && (
        <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded p-2 mb-4">{error}</p>
      )}

      {lineups.length > 0 && (
        <>
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
            {lineups.length} combinaciones · ordenadas por Net Rating
          </p>
        </>
      )}

      {!loading && lineups.length === 0 && selectedTeam && (
        <p className="text-gray-400 text-sm text-center mt-8">
          Selecciona un equipo y pulsa «Analizar» para ver los quintetos.
        </p>
      )}
    </div>
  )
}
