/**
 * ShotChartPage — Fase 3
 * Cancha FIBA SVG interactiva con heatmap de zonas por eficiencia.
 * Solo disponible para colecciones FEB (FBCYL no dispone de coordenadas de tiro).
 */
import { useState, useMemo, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Target, ChevronDown } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getShotZones, getShotRaw, getPlayerStats, type ShotZoneData, type PlayerStat, type ShotRawData } from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'
import FibaCourtSVG from '@/components/ui/FibaCourtSVG'
import ExportButton from '@/components/ui/ExportButton'
import Tooltip from '@/components/ui/Tooltip'
import { STAT_LABELS } from '@/lib/statLabels'

// -- Helpers ------------------------------------------------------------------

function clsForPct(pct: number): string {
  if (pct >= 45) return 'text-green-400'
  if (pct >= 35) return 'text-yellow-400'
  if (pct >= 25) return 'text-orange-400'
  return 'text-red-400'
}

// -- Component ----------------------------------------------------------------

export default function ShotChartPage() {
  const { collection } = useCollection()

  const [viewMode, setViewMode] = useState<'team' | 'player'>('team')
  const [selectedTeam, setSelectedTeam] = useState<string>('')
  const [selectedPlayer, setSelectedPlayer] = useState<string>('')
  const [highlightZone, setHighlightZone] = useState<string | null>(null)
  const [vizMode, setVizMode] = useState<'zones' | 'scatter' | 'heatmap'>('zones')
  const [shotFilter, setShotFilter] = useState<'all' | 'made' | 'missed'>('all')

  const isFbcyl = collection?.isFbcyl ?? false

  // Fetch team list for selector
  const { data: teamList = [] } = useQuery<string[]>({
    queryKey: ['team-list', collection?.name],
    queryFn: () =>
      fetch(`/api/v1/teams/${encodeURIComponent(collection!.name)}/teams`).then(r => r.json()),
    enabled: Boolean(collection) && !isFbcyl,
    staleTime: 10 * 60_000,
  })

  // Load players whenever a team is selected (pre-caches for player mode)
  const { data: playerList = [] } = useQuery<PlayerStat[]>({
    queryKey: ['shot-player-list', collection?.name],
    queryFn: () => getPlayerStats(collection!.name),
    enabled: Boolean(collection) && !isFbcyl && Boolean(selectedTeam),
    staleTime: 10 * 60_000,
  })

  // Changing mode never changes selectedTeam; only reset the player selection
  useEffect(() => {
    setSelectedPlayer('')
  }, [viewMode])

  const hasFilter = viewMode === 'team' ? Boolean(selectedTeam) : Boolean(selectedPlayer)

  // Fetch shot zones for selected team or player
  const { data: zones = [], isLoading } = useQuery<ShotZoneData[]>({
    queryKey: ['shot-zones', collection?.name, viewMode, selectedTeam, selectedPlayer],
    queryFn: () =>
      viewMode === 'team'
        ? getShotZones(collection!.name, { team: selectedTeam || undefined })
        : getShotZones(collection!.name, { player: selectedPlayer || undefined }),
    enabled: Boolean(collection) && !isFbcyl && hasFilter,
    staleTime: 5 * 60_000,
  })

  // Fetch individual shot coordinates for scatter / heatmap modes
  const { data: rawShots = [], isLoading: rawLoading } = useQuery<ShotRawData[]>({
    queryKey: ['shot-raw', collection?.name, viewMode, selectedTeam, selectedPlayer],
    queryFn: () =>
      viewMode === 'team'
        ? getShotRaw(collection!.name, { team: selectedTeam || undefined })
        : getShotRaw(collection!.name, { player: selectedPlayer || undefined }),
    enabled: Boolean(collection) && !isFbcyl && hasFilter && vizMode !== 'zones',
    staleTime: 5 * 60_000,
  })

  const totalFga = useMemo(() => zones.reduce((s, z) => s + z.fga, 0), [zones])
  const totalFgm = useMemo(() => zones.reduce((s, z) => s + z.fgm, 0), [zones])
  const hasAnyData = useMemo(() => zones.some(z => z.fga > 0), [zones])

  // Client-side made/missed filter for scatter and heatmap
  const filteredShots = useMemo(() =>
    shotFilter === 'all' ? rawShots :
    rawShots.filter(s => shotFilter === 'made' ? s.made : !s.made),
  [rawShots, shotFilter])

  const anyLoading = isLoading || (vizMode !== 'zones' && rawLoading)

  // Players of the selected team, sorted by PPG desc for easy scanning
  const teamPlayers = useMemo(() =>
    playerList
      .filter(p => p.team_name === selectedTeam)
      .sort((a, b) => b.points_per_game - a.points_per_game),
  [playerList, selectedTeam])

  const courtRef = useRef<SVGSVGElement>(null)

  const zonesCsvHeaders: { key: string; label: string }[] = [
    { key: 'zone_label', label: 'Zona' },
    { key: 'fgm',        label: 'T.I.' },
    { key: 'fga',        label: 'T.A.' },
    { key: 'fg_pct',     label: '%TF' },
    { key: 'points',     label: 'Tipo' },
  ]

  const exportLabel = useMemo(() => {
    if (viewMode === 'player' && selectedPlayer) {
      return playerList.find(p => p.player_id === selectedPlayer)?.player_name ?? selectedPlayer
    }
    return selectedTeam
  }, [viewMode, selectedPlayer, selectedTeam, playerList])

  if (isFbcyl) {
    return (
      <PageTransition>
        <div className="space-y-4">
          <div>
            <h1 className="text-2xl font-bold text-ink-primary">Gráficos de Tiro</h1>
            <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
          </div>
          <div className="card p-10 flex flex-col items-center gap-3 text-center">
            <Target className="w-10 h-10 text-ink-secondary opacity-40" />
            <p className="text-ink-primary font-medium">No disponible para FBCYL</p>
            <p className="text-ink-secondary text-sm max-w-sm">
              Las colecciones FBCYL no incluyen coordenadas individuales de tiro.
              Esta función está disponible únicamente en colecciones FEB.
            </p>
          </div>
        </div>
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h1 className="text-2xl font-bold text-ink-primary">Gráficos de Tiro</h1>
            <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
          </div>
          <ExportButton
            filename={`tiros_${exportLabel}_${collection?.name ?? ''}`}
            captureRef={courtRef as unknown as import('react').RefObject<HTMLElement>}
            pdfTitle={`Gráfico de Tiro — ${exportLabel || 'selección'} — ${collection?.label ?? ''}`}
            csvData={zones.map(z => ({ ...z, points: z.points === 3 ? '3P' : '2P' }))}
            csvHeaders={zonesCsvHeaders}
          />
        </div>

        {/* Controls */}
        <div className="card p-4 flex flex-wrap gap-3 items-center">
          {/* View mode */}
          <div className="flex rounded-lg overflow-hidden border border-surface-border text-sm">
            {(['team', 'player'] as const).map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-4 py-1.5 font-medium transition-colors ${
                  viewMode === mode
                    ? 'bg-accent-500 text-white'
                    : 'text-ink-secondary hover:bg-surface-hover'
                }`}
              >
                {mode === 'team' ? 'Equipo' : 'Jugador'}
              </button>
            ))}
          </div>

          {/* Team selector — shared between both modes */}
          <div className="relative">
            <select
              value={selectedTeam}
              onChange={e => { setSelectedTeam(e.target.value); setSelectedPlayer('') }}
              className="appearance-none bg-surface-base border border-surface-border rounded-lg px-3 py-1.5 pr-8 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400"
            >
              <option value="">— Selecciona equipo —</option>
              {teamList.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-secondary" />
          </div>

          {/* Active player chip — shown in player mode once a player is picked from the table */}
          {viewMode === 'player' && selectedPlayer && (() => {
            const p = playerList.find(pl => pl.player_id === selectedPlayer)
            return p ? (
              <span className="flex items-center gap-1.5 bg-accent-500/20 text-accent-300 text-xs font-medium px-2.5 py-1 rounded-full">
                {p.player_name}
                <button
                  onClick={() => setSelectedPlayer('')}
                  className="hover:text-white transition-colors leading-none ml-0.5"
                  aria-label="Quitar selección de jugador"
                >✕</button>
              </span>
            ) : null
          })()}

          {/* Visualization mode toggle */}
          <div className="flex rounded-lg overflow-hidden border border-surface-border text-sm ml-auto">
            {(['zones', 'scatter', 'heatmap'] as const).map(mode => (
              <button
                key={mode}
                onClick={() => setVizMode(mode)}
                className={`px-3 py-1.5 font-medium transition-colors ${
                  vizMode === mode
                    ? 'bg-accent-500 text-white'
                    : 'text-ink-secondary hover:bg-surface-hover'
                }`}
              >
                {mode === 'zones' ? 'Zonas' : mode === 'scatter' ? 'Scatter' : 'Calor'}
              </button>
            ))}
          </div>

          {/* Shot result filter — scatter and heatmap only */}
          {vizMode !== 'zones' && (
            <div className="flex rounded-lg overflow-hidden border border-surface-border text-sm">
              {(['all', 'made', 'missed'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setShotFilter(f)}
                  className={`px-3 py-1.5 font-medium transition-colors flex items-center gap-1.5 ${
                    shotFilter === f
                      ? 'bg-accent-500 text-white'
                      : 'text-ink-secondary hover:bg-surface-hover'
                  }`}
                >
                  {f !== 'all' && (
                    <span className={`w-2 h-2 rounded-full inline-block flex-shrink-0 ${
                      f === 'made' ? 'bg-green-400' : 'bg-red-400'
                    }`} />
                  )}
                  {f === 'all' ? 'Todos' : f === 'made' ? 'Aciertos' : 'Fallos'}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Main layout: court + stats */}
        <div className="grid grid-cols-1 lg:grid-cols-[auto_1fr] gap-4">
          {/* Court */}
          <div className="card p-4 flex flex-col items-center gap-2">
            {anyLoading ? (
              <div className="w-[450px] h-[420px] flex items-center justify-center">
                <div className="w-8 h-8 border-2 border-accent-400 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <FibaCourtSVG
                svgRef={courtRef}
                zones={hasFilter && vizMode === 'zones' ? zones : []}
                vizMode={vizMode}
                rawShots={vizMode !== 'zones' ? filteredShots : undefined}
                onZoneClick={vizMode === 'zones' ? setHighlightZone : undefined}
                highlightZone={vizMode === 'zones' ? highlightZone : null}
              />
            )}
            {/* Legend */}
            {vizMode === 'zones' ? (
              <div className="flex items-center gap-4 mt-1 text-xs text-ink-secondary">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded-full inline-block bg-red-500 opacity-80" />
                  Bajo (&lt;25%)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded-full inline-block bg-yellow-400 opacity-80" />
                  Medio (25–35%)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded-full inline-block bg-green-500 opacity-80" />
                  Alto (&gt;35%)
                </span>
                <span className="ml-2 italic">Tamaño = volumen</span>
              </div>
            ) : vizMode === 'scatter' ? (
              <div className="flex items-center gap-4 mt-1 text-xs text-ink-secondary">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded-full inline-block bg-green-400 opacity-80" />
                  Acierto
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded-full inline-block bg-red-400 opacity-80" />
                  Fallo
                </span>
                <span className="ml-2 italic">{filteredShots.length} tiros</span>
              </div>
            ) : (
              <div className="flex items-center gap-4 mt-1 text-xs text-ink-secondary">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded-full inline-block bg-orange-400 opacity-80" />
                  Densidad de tiros
                </span>
                <span className="ml-2 italic">{filteredShots.length} tiros</span>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-4">

            {/* Player picker — visible in player mode once a team is selected */}
            {viewMode === 'player' && selectedTeam && (
              <div className="card p-0 overflow-hidden">
                <div className="p-3 border-b border-surface-border">
                  <p className="text-sm font-medium text-ink-primary">Jugadores — {selectedTeam}</p>
                  <p className="text-xs text-ink-secondary mt-0.5">Clic en una fila para ver el mapa de tiro individual</p>
                </div>
                {teamPlayers.length === 0 ? (
                  <div className="p-6 flex justify-center">
                    <div className="w-5 h-5 border-2 border-accent-400 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : (
                  <div className="overflow-y-auto max-h-56">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-surface-base z-10">
                        <tr className="text-xs text-ink-secondary uppercase tracking-wide border-b border-surface-border/50">
                          <th className="px-3 py-2 text-left font-medium">Jugador</th>
                          <th className="px-3 py-2 text-right font-medium">Min</th>
                          <th className="px-3 py-2 text-right font-medium">Pts</th>
                          <th className="px-3 py-2 text-right font-medium">%2P</th>
                          <th className="px-3 py-2 text-right font-medium">%3P</th>
                        </tr>
                      </thead>
                      <tbody>
                        {teamPlayers.map(p => (
                          <tr
                            key={p.player_id}
                            onClick={() => setSelectedPlayer(prev => prev === p.player_id ? '' : p.player_id)}
                            className={`border-t border-surface-border/50 cursor-pointer transition-colors ${
                              selectedPlayer === p.player_id
                                ? 'bg-accent-500/15'
                                : 'hover:bg-surface-hover/50'
                            }`}
                          >
                            <td className={`px-3 py-2 font-medium ${
                              selectedPlayer === p.player_id ? 'text-accent-300' : 'text-ink-primary'
                            }`}>{p.player_name}</td>
                            <td className="px-3 py-2 text-right tabular-nums text-ink-secondary">
                              {p.minutes_per_game.toFixed(0)}
                            </td>
                            <td className="px-3 py-2 text-right tabular-nums text-ink-secondary">
                              {p.points_per_game.toFixed(1)}
                            </td>
                            <td className={`px-3 py-2 text-right tabular-nums font-medium ${
                              p.fg2_percentage != null ? clsForPct(p.fg2_percentage) : 'text-ink-secondary'
                            }`}>
                              {p.fg2_percentage != null ? `${p.fg2_percentage.toFixed(0)}%` : '—'}
                            </td>
                            <td className={`px-3 py-2 text-right tabular-nums font-medium ${
                              p.fg3_percentage != null ? clsForPct(p.fg3_percentage) : 'text-ink-secondary'
                            }`}>
                              {p.fg3_percentage != null ? `${p.fg3_percentage.toFixed(0)}%` : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Zone stats */}
            <div className="card p-0 overflow-hidden">
              <div className="p-3 border-b border-surface-border">
                <p className="text-sm font-medium text-ink-primary">Estadísticas por Zona</p>
                {totalFga > 0 && (
                  <p className="text-xs text-ink-secondary mt-0.5">
                    Total: {totalFgm}/{totalFga} ({(totalFgm / totalFga * 100).toFixed(1)}%)
                  </p>
                )}
              </div>
              {!hasFilter ? (
                <div className="p-8 text-center text-ink-secondary text-sm">
                  {viewMode === 'player' && selectedTeam
                    ? 'Selecciona un jugador de la tabla para ver su mapa de tiro'
                    : viewMode === 'player'
                    ? 'Selecciona un equipo para acceder a los jugadores'
                    : 'Selecciona un equipo para ver estadísticas por zona'}
                </div>
              ) : anyLoading ? (
                <div className="p-8 flex justify-center">
                  <div className="w-6 h-6 border-2 border-accent-400 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : !hasAnyData ? (
                <div className="p-8 text-center text-ink-secondary text-sm">
                  No se encontraron datos de lanzamiento para esta selección.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-ink-secondary uppercase tracking-wide">
                      <th className="px-3 py-2 text-left font-medium">Zona</th>
                      <th className="px-3 py-2 text-right font-medium">
                        <Tooltip text={`${STAT_LABELS['T.I.'].label}: ${STAT_LABELS['T.I.'].description}`}>T.I.</Tooltip>
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        <Tooltip text={`${STAT_LABELS['T.A.'].label}: ${STAT_LABELS['T.A.'].description}`}>T.A.</Tooltip>
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        <Tooltip text={`${STAT_LABELS['%TF'].label}: ${STAT_LABELS['%TF'].description}`}>%TF</Tooltip>
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        <Tooltip text={`${STAT_LABELS['Pts'].label}: ${STAT_LABELS['Pts'].description}`}>Pts</Tooltip>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {zones.map(z => (
                      <tr
                        key={z.zone}
                        onClick={() => setHighlightZone(prev => prev === z.zone ? null : z.zone)}
                        className={`border-t border-surface-border/50 cursor-pointer transition-colors ${
                          highlightZone === z.zone ? 'bg-surface-hover' : 'hover:bg-surface-hover/50'
                        }`}
                      >
                        <td className="px-3 py-2 text-ink-primary">
                          <span className="flex items-center gap-1.5">
                            <span
                              className="w-2 h-2 rounded-full inline-block flex-shrink-0"
                              style={{ backgroundColor: z.fga > 0 ? `hsl(${Math.min(Math.round(z.fg_pct / 40 * 120), 120)}, 85%, 42%)` : '#444' }}
                            />
                            {z.zone_label}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-ink-secondary">{z.fgm}</td>
                        <td className="px-3 py-2 text-right tabular-nums text-ink-secondary">{z.fga}</td>
                        <td className={`px-3 py-2 text-right tabular-nums font-medium ${z.fga > 0 ? clsForPct(z.fg_pct) : 'text-ink-secondary'}`}>
                          {z.fga > 0 ? `${z.fg_pct.toFixed(1)}%` : '—'}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-ink-secondary">
                          {z.points === 3 ? '3P' : '2P'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

          </div>
        </div>
      </div>
    </PageTransition>
  )
}
