import { useState, useRef, useMemo, useEffect, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { useCollection } from '@/context/CollectionContext'
import PageTransition from '@/components/ui/PageTransition'
import ExportButton from '@/components/ui/ExportButton'
import {
  getLineupAnalysis, getTeamStats,
  LINEUP_STAT_GROUPS,
  type LineupRow, type GameLogEntry,
} from '@/api/client'

/** Stats where lower values are better (sort ascending). */
const REVERSE_STATS = new Set(['drtg', 'tov_pct'])
const ALL_STAT_OPTIONS = LINEUP_STAT_GROUPS.flatMap(g => g.options)

/** Deterministic hue (0-360) derived from a player name string. */
function nameHue(name: string): number {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffff
  return h % 360
}

/** Extract 2-letter initials from a player name.
 *  Handles "SURNAME, NAME" (FBCYL) and "Name Surname" (FEB) formats. */
function initials(name: string): string {
  if (!name || name.startsWith('Player ')) return '?'
  const commaIdx = name.indexOf(',')
  if (commaIdx !== -1) {
    // "APELLIDO [APELLIDO2], NOMBRE [NOMBRE2]"
    const given  = name.slice(commaIdx + 1).trim()
    const family = name.slice(0, commaIdx).trim()
    return ((given[0] ?? '') + (family[0] ?? '')).toUpperCase()
  }
  // Space-separated "Nombre Apellido"
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts[parts.length - 1]?.[0] ?? '')).toUpperCase()
}

/** Small circular avatar chip: shows player photo with initials fallback + name tooltip. */
function PlayerAvatar({ name, photoUrl }: { name: string; photoUrl?: string }) {
  const [imgFailed, setImgFailed] = useState(false)
  const hue = nameHue(name)
  const ini = initials(name)

  if (photoUrl && !imgFailed) {
    return (
      <span
        title={name}
        className="inline-flex items-center justify-center rounded-full overflow-hidden flex-shrink-0 cursor-default border-2 border-surface-border"
        style={{ width: 28, height: 28 }}
      >
        <img
          src={photoUrl}
          alt={name}
          className="w-full h-full object-cover"
          onError={() => setImgFailed(true)}
        />
      </span>
    )
  }

  return (
    <span
      title={name}
      className="inline-flex items-center justify-center rounded-full text-white font-semibold select-none cursor-default flex-shrink-0"
      style={{
        width: 28, height: 28, fontSize: 10,
        background: `hsl(${hue},55%,45%)`,
        border: '2px solid rgba(255,255,255,0.25)',
      }}
    >
      {ini}
    </span>
  )
}

function fmtStat(val: number | undefined, key: string): string {
  if (val == null) return '\u2014'
  if (key === 'ftr') return val.toFixed(2)
  if (['efg_pct', 'tov_pct', 'orb_pct'].includes(key)) return `${val.toFixed(1)}%`
  if (key === 'plus_minus') return val > 0 ? `+${val}` : String(val)
  return val.toFixed(1)
}

function fmtDiff(diff: number, key: string): string {
  const v = key === 'ftr' ? Math.abs(diff).toFixed(2) : Math.abs(diff).toFixed(1)
  if (diff > 0) return `+${v}`
  if (diff < 0) return `-${v}`
  return '0'
}

const selectCls =
  'appearance-none bg-surface-base border border-surface-border rounded-lg px-3 py-1.5 text-sm ' +
  'text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400'

interface Team { name: string; id: string }
interface AnalysisParams { teamId: string; teamName: string; size: number; stat: string; period: number }

/**
 * Player combination analysis page.
 * Shows the best and worst N combinations of 2-5 players sorted by a
 * selectable stat, plus a per-player frequency table and a per-game chart
 * for any selected lineup.
 */
export default function LineupsPage() {
  const { collection } = useCollection()

  // Form state
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null)
  const [size, setSize] = useState(5)
  const [stat, setStat] = useState('net_rating')
  const [period, setPeriod] = useState(0)
  const [topN, setTopN] = useState(5)

  // Trigger for the analysis query (set when user presses "Analizar")
  const [analysisParams, setAnalysisParams] = useState<AnalysisParams | null>(null)

  // Row selected for the game-log panel
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)

  const exportRef = useRef<HTMLDivElement>(null)

  // Team list
  const { data: teamData } = useQuery({
    queryKey: ['team-list-lineups', collection?.name],
    queryFn: () => getTeamStats(collection!.name),
    enabled: Boolean(collection),
    staleTime: 10 * 60_000,
  })
  const teams = useMemo(
    () =>
      (teamData?.team_stats ?? [])
        .map(t => ({ name: t.team_name, id: String(t.team_id ?? t.team_name) }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [teamData],
  )
  useEffect(() => {
    if (teams.length > 0 && !selectedTeam) setSelectedTeam(teams[0])
  }, [teams, selectedTeam])

  // Lineup analysis query
  const { data: lineups = [], isFetching, error } = useQuery({
    queryKey: ['lineups', collection?.name, analysisParams],
    queryFn: () =>
      getLineupAnalysis(
        collection!.name,
        analysisParams!.teamId,
        analysisParams!.teamName,
        analysisParams!.size,
        analysisParams!.stat,
        analysisParams!.period,
        true, // always include game_log
      ),
    enabled: Boolean(collection && analysisParams),
    staleTime: 5 * 60_000,
  })

  // Derived data
  const activeStat = analysisParams?.stat ?? stat
  const isReverse = REVERSE_STATS.has(activeStat)
  const statLabel = ALL_STAT_OPTIONS.find(o => o.key === activeStat)?.label ?? activeStat

  // Cap topN to avoid top/bottom overlap
  const n = Math.min(topN, Math.floor(lineups.length / 2))
  const topRows = lineups.slice(0, n)
  const bottomRows = lineups.length > n ? lineups.slice(-n) : []

  // Reference values for the "Dif." column
  const topRef = topRows[0]?.[activeStat] as number | undefined
  const bottomRef = bottomRows[bottomRows.length - 1]?.[activeStat] as number | undefined

  // Player frequency across top N / bottom N
  const playerFrequency = useMemo(() => {
    const freq: Record<string, { top: number; bottom: number }> = {}
    topRows.forEach(row => {
      ;(row.players as string[]).forEach(p => {
        freq[p] ??= { top: 0, bottom: 0 }
        freq[p].top++
      })
    })
    bottomRows.forEach(row => {
      ;(row.players as string[]).forEach(p => {
        freq[p] ??= { top: 0, bottom: 0 }
        freq[p].bottom++
      })
    })
    return Object.entries(freq)
      .filter(([, v]) => v.top > 0 || v.bottom > 0)
      .sort((a, b) => (b[1].top - a[1].top) || (a[1].bottom - b[1].bottom))
  }, [topRows, bottomRows])

  // Game log for the selected lineup with cumulative average
  const selectedLineup = selectedIdx != null
    ? ([...topRows, ...bottomRows] as LineupRow[])[selectedIdx]
    : null
  const gameLog = useMemo<(GameLogEntry & { cumulative_avg: number })[]>(() => {
    const raw = selectedLineup?.game_log as GameLogEntry[] | undefined
    if (!raw?.length) return []
    const sorted = [...raw].sort((a, b) => a.date.localeCompare(b.date))
    let sum = 0
    return sorted.map((entry, i) => {
      sum += (entry as unknown as Record<string, number>)[activeStat] ?? 0
      return { ...entry, cumulative_avg: Math.round((sum / (i + 1)) * 10) / 10 }
    })
  }, [selectedLineup, activeStat])

  // CSV export data
  const csvData = useMemo(
    () =>
      lineups.map(row => ({
        jugadoras:    (row.players as string[]).join(' - '),
        min:          row.minutes?.toFixed(1),
        partidos:     row.games_played ?? '',
        pf:           row.points_for,
        pc:           row.points_against,
        plus_minus:   row.plus_minus,
        net_rating:   row.net_rating,
        ortg:         row.ortg ?? '',
        drtg:         row.drtg ?? '',
        efg_pct:      row.efg_pct ?? '',
        tov_pct:      row.tov_pct ?? '',
        orb_pct:      row.orb_pct ?? '',
        ftr:          row.ftr ?? '',
        ast:          row.ast ?? '',
        trb:          row.trb ?? '',
      })),
    [lineups],
  )
  const csvHeaders = [
    { key: 'jugadoras',  label: 'Combinacion' },
    { key: 'min',        label: 'MIN' },
    { key: 'partidos',   label: 'PJ' },
    { key: 'pf',         label: 'PF' },
    { key: 'pc',         label: 'PC' },
    { key: 'plus_minus', label: '+/-' },
    { key: 'net_rating', label: 'Net Rtg' },
    { key: 'ortg',       label: 'ORtg' },
    { key: 'drtg',       label: 'DRtg' },
    { key: 'efg_pct',    label: 'eFG%' },
    { key: 'tov_pct',    label: 'TOV%' },
    { key: 'orb_pct',    label: 'ORB%' },
    { key: 'ftr',        label: 'FTr' },
    { key: 'ast',        label: 'AST' },
    { key: 'trb',        label: 'REB' },
  ]

  // Handlers
  function handleAnalyze(e: FormEvent) {
    e.preventDefault()
    if (!selectedTeam) return
    setSelectedIdx(null)
    setAnalysisParams({
      teamId:   selectedTeam.id,
      teamName: selectedTeam.name,
      size,
      stat,
      period,
    })
  }

  function rowDiff(val: number | undefined, ref: number | undefined) {
    if (val == null || ref == null) return null
    return fmtDiff(val - ref, activeStat)
  }

  function renderRow(row: LineupRow, idx: number, group: 'top' | 'bottom') {
    const compositeIdx = group === 'top' ? idx : n + idx
    const isSelected = compositeIdx === selectedIdx
    const val = row[activeStat] as number | undefined
    const ref = group === 'top' ? topRef : bottomRef
    const diff = rowDiff(val, ref)
    const diffNum = val != null && ref != null ? val - ref : null
    const diffCls = diffNum == null ? ''
      : diffNum > 0 ? 'text-green-700 dark:text-green-400'
      : diffNum < 0 ? 'text-red-600 dark:text-red-400'
      : 'text-ink-secondary'
    const rowCls = group === 'top'
      ? 'bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/40'
      : 'bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/40'

    return (
      <tr
        key={compositeIdx}
        onClick={() => setSelectedIdx(isSelected ? null : compositeIdx)}
        className={`cursor-pointer transition-colors ${rowCls} ${isSelected ? 'outline outline-2 outline-accent-400' : ''}`}
      >
        <td className="px-3 py-2 font-medium text-ink-primary text-xs">
          <div className="flex flex-wrap items-center gap-1">
            {(row.players as string[]).map((name, i) => (
              <PlayerAvatar
                key={i}
                name={name}
                photoUrl={(row.player_photo_urls as string[] | undefined)?.[i]}
              />
            ))}
          </div>
        </td>
        <td className="px-3 py-2 text-center text-ink-secondary">{row.minutes?.toFixed(1)}</td>
        <td className="px-3 py-2 text-center text-ink-secondary">{row.games_played ?? '\u2014'}</td>
        <td className="px-3 py-2 text-center">{row.points_for}</td>
        <td className="px-3 py-2 text-center">{row.points_against}</td>
        <td className="px-3 py-2 text-center font-semibold">
          {fmtStat(val, activeStat)}
        </td>
        <td className={`px-3 py-2 text-center text-xs font-semibold ${diffCls}`}>
          {diff ?? '\u2014'}
        </td>
      </tr>
    )
  }

  // Render
  return (
    <PageTransition>
      <div className="space-y-4">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h1 className="text-2xl font-bold text-ink-primary">{`An\u00e1lisis de Combinaciones`}</h1>
            <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
          </div>
          {lineups.length > 0 && (
            <ExportButton
              filename={`combinaciones_${activeStat}_${collection?.name ?? ''}`}
              captureRef={exportRef}
              pdfTitle={`An\u00e1lisis de Combinaciones \u2014 ${statLabel} \u2014 ${collection?.label ?? ''}`}
              csvData={csvData}
              csvHeaders={csvHeaders}
            />
          )}
        </div>

        {/* Controls */}
        <form onSubmit={handleAnalyze} className="card p-4 flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs font-medium text-ink-secondary mb-1">Equipo</label>
            <select
              value={selectedTeam?.id ?? ''}
              onChange={e => setSelectedTeam(teams.find(t => t.id === e.target.value) ?? null)}
              className={selectCls}
            >
              {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-ink-secondary mb-1">Jugadoras</label>
            <select value={size} onChange={e => setSize(Number(e.target.value))} className={selectCls}>
              {[2, 3, 4, 5].map(v => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-ink-secondary mb-1">{`Estad\u00edstica`}</label>
            <select value={stat} onChange={e => setStat(e.target.value)} className={selectCls}>
              {LINEUP_STAT_GROUPS.map(g => (
                <optgroup key={g.label} label={g.label}>
                  {g.options.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
                </optgroup>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-ink-secondary mb-1">{`Per\u00edodo`}</label>
            <select value={period} onChange={e => setPeriod(Number(e.target.value))} className={selectCls}>
              <option value={0}>Temporada completa</option>
              <option value={7}>{`\u00daltimos 7 d\u00edas`}</option>
              <option value={15}>{`\u00daltimos 15 d\u00edas`}</option>
              <option value={30}>{`\u00daltimos 30 d\u00edas`}</option>
              <option value={60}>{`\u00daltimos 60 d\u00edas`}</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-ink-secondary mb-1">Top / Bottom N</label>
            <input
              type="number" min={1} max={20} value={topN}
              onChange={e => setTopN(Math.max(1, Math.min(20, Number(e.target.value))))}
              className={`${selectCls} w-20`}
            />
          </div>

          <button
            type="submit"
            disabled={isFetching || !selectedTeam}
            className="bg-accent-600 hover:bg-accent-700 disabled:opacity-60 text-white text-sm font-medium rounded-lg px-5 py-1.5 transition-colors"
          >
            {isFetching ? 'Analizando\u2026' : 'Analizar'}
          </button>
        </form>

        {/* Error */}
        {error && (
          <p className="text-red-600 text-sm bg-red-50 dark:bg-red-900/20 border border-red-200 rounded-lg p-3">
            {error instanceof Error ? error.message : 'Error al analizar combinaciones'}
          </p>
        )}

        {/* Loading indicator */}
        {isFetching && (
          <div className="flex items-center gap-3 text-ink-secondary text-sm card p-4">
            <span className="inline-block w-4 h-4 border-2 border-accent-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
            {`Analizando partidos\u2026 esto puede tardar hasta un minuto en temporadas largas.`}
          </div>
        )}

        {/* Results */}
        {!isFetching && lineups.length > 0 && (
          <div ref={exportRef} className="space-y-4">

            <p className="text-ink-secondary text-xs">
              {lineups.length}{` combinaciones encontradas \u00b7 m\u00edn. 15 min totales / 5 partidos \u00b7`}
              top/bottom <strong>{n}</strong> por <strong>{statLabel}</strong>
              {isReverse ? ' (menor = mejor)' : ' (mayor = mejor)'}
              {' \u00b7 '}{`haz clic en una fila para ver la evoluci\u00f3n por partido`}
            </p>

            {/* Main table */}
            <div className="overflow-x-auto rounded-xl border border-surface-border shadow-sm">
              <table className="w-full text-sm">
                <thead className="bg-court-950 text-white">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold">{`Combinaci\u00f3n`}</th>
                    <th className="px-3 py-2 text-center font-semibold w-14">MIN</th>
                    <th className="px-3 py-2 text-center font-semibold w-12">PJ</th>
                    <th className="px-3 py-2 text-center font-semibold w-14">PF</th>
                    <th className="px-3 py-2 text-center font-semibold w-14">PC</th>
                    <th className="px-3 py-2 text-center font-semibold w-24">{statLabel}</th>
                    <th className="px-3 py-2 text-center font-semibold w-14">Dif.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {topRows.map((row, i) => renderRow(row, i, 'top'))}
                  <tr aria-hidden="true"><td colSpan={7} className="h-1.5 bg-gray-300 dark:bg-gray-600" /></tr>
                  {bottomRows.map((row, i) => renderRow(row, i, 'bottom'))}
                </tbody>
              </table>
            </div>

            {/* Game log panel */}
            {selectedLineup && gameLog.length > 0 && (
              <div className="card p-4 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-xs text-ink-secondary uppercase tracking-wide mb-0.5">{`Evoluci\u00f3n por partido`}</p>
                    <div className="flex flex-wrap items-center gap-1 mt-1">
                      {(selectedLineup.players as string[]).map((name, i) => (
                        <PlayerAvatar
                          key={i}
                          name={name}
                          photoUrl={(selectedLineup.player_photo_urls as string[] | undefined)?.[i]}
                        />
                      ))}
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedIdx(null)}
                    className="text-ink-secondary hover:text-ink-primary transition-colors flex-shrink-0"
                    aria-label="Cerrar panel"
                  >
                    <X size={18} />
                  </button>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={gameLog} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(156,163,175,0.3)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
                    <YAxis tick={{ fontSize: 10 }} width={38} />
                    <Tooltip
                      labelFormatter={d => `Partido: ${d}`}
                      formatter={(v: number) => [fmtStat(v, activeStat), '']}
                    />
                    <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="2 2" />
                    <Line
                      type="monotone" dataKey={activeStat}
                      stroke="#f97316" strokeWidth={2} dot={{ r: 3 }} name={statLabel}
                    />
                    <Line
                      type="monotone" dataKey="cumulative_avg"
                      stroke="#6366f1" strokeWidth={1.5} strokeDasharray="4 2"
                      dot={false} name="Media acum."
                    />
                  </LineChart>
                </ResponsiveContainer>
                <p className="text-xs text-ink-secondary text-center">
                  <span className="inline-block w-5 border-t-2 border-orange-400 mr-1.5 align-middle" />Valor por partido
                  &nbsp;&middot;&nbsp;
                  <span className="inline-block w-5 border-t-2 border-dashed border-indigo-500 mr-1.5 align-middle" />Media acumulada
                </p>
              </div>
            )}

            {/* Player frequency table */}
            {playerFrequency.length > 0 && (
              <div className="card p-4">
                <h3 className="text-sm font-semibold text-ink-primary mb-3">
                  Frecuencia de jugadoras en top / bottom {n}
                </h3>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-ink-secondary border-b border-surface-border">
                      <th className="text-left pb-2 font-medium">Jugadora</th>
                      <th className="text-right pb-2 font-medium w-8 pr-2">Top</th>
                      <th className="pb-2 w-36" />
                      <th className="text-right pb-2 font-medium w-8 pr-2">Bot.</th>
                      <th className="pb-2 w-36" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {playerFrequency.map(([player, freq]) => (
                      <tr key={player} className="hover:bg-surface-hover transition-colors">
                        <td className="py-1.5 pr-3 text-ink-primary">{player}</td>
                        <td className="py-1.5 text-right text-xs font-semibold text-green-700 dark:text-green-400 pr-2">
                          {freq.top}/{n}
                        </td>
                        <td className="py-1.5 pr-3">
                          <div className="w-full bg-surface-border rounded-full h-2.5 overflow-hidden">
                            <div
                              className="h-full bg-green-400 rounded-full transition-all"
                              style={{ width: `${(freq.top / n) * 100}%` }}
                            />
                          </div>
                        </td>
                        <td className="py-1.5 text-right text-xs font-semibold text-red-600 dark:text-red-400 pr-2">
                          {freq.bottom}/{n}
                        </td>
                        <td className="py-1.5">
                          <div className="w-full bg-surface-border rounded-full h-2.5 overflow-hidden">
                            <div
                              className="h-full bg-red-400 rounded-full transition-all"
                              style={{ width: `${(freq.bottom / n) * 100}%` }}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Empty states */}
        {!isFetching && lineups.length === 0 && analysisParams && !error && (
          <p className="text-ink-secondary text-sm text-center mt-8">
            {`No se encontraron combinaciones con los filtros seleccionados (m\u00edn. 15 min totales y 5 partidos).`}
          </p>
        )}
        {!analysisParams && !isFetching && (
          <p className="text-ink-secondary text-sm text-center mt-8">
            {`Selecciona un equipo y pulsa \u00abAnalizar\u00bb para ver las combinaciones.`}
          </p>
        )}

      </div>
    </PageTransition>
  )
}