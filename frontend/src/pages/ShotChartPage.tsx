/**
 * ShotChartPage — Fase 3
 * Cancha FIBA SVG interactiva con heatmap de zonas por eficiencia.
 * Solo disponible para colecciones FEB (FBCYL no dispone de coordenadas de tiro).
 */
import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Target, ChevronDown } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getShotZones, type ShotZoneData } from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'
import FibaCourtSVG from '@/components/ui/FibaCourtSVG'
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
  const [highlightZone, setHighlightZone] = useState<string | null>(null)

  const isFbcyl = collection?.isFbcyl ?? false

  // Fetch team list for selector
  const { data: teamList = [] } = useQuery<string[]>({
    queryKey: ['team-list', collection?.name],
    queryFn: () =>
      fetch(`/api/v1/teams/${encodeURIComponent(collection!.name)}/teams`).then(r => r.json()),
    enabled: Boolean(collection) && !isFbcyl,
    staleTime: 10 * 60_000,
  })

  // Fetch shot zones for selected team
  const { data: zones = [], isLoading } = useQuery<ShotZoneData[]>({
    queryKey: ['shot-zones', collection?.name, selectedTeam],
    queryFn: () =>
      getShotZones(collection!.name, { team: selectedTeam || undefined }),
    enabled: Boolean(collection) && !isFbcyl && Boolean(selectedTeam),
    staleTime: 5 * 60_000,
  })

  const totalFga = useMemo(() => zones.reduce((s, z) => s + z.fga, 0), [zones])
  const totalFgm = useMemo(() => zones.reduce((s, z) => s + z.fgm, 0), [zones])

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

          {/* Team selector */}
          {viewMode === 'team' && (
            <div className="relative">
              <select
                value={selectedTeam}
                onChange={e => setSelectedTeam(e.target.value)}
                className="appearance-none bg-surface-base border border-surface-border rounded-lg px-3 py-1.5 pr-8 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400"
              >
                <option value="">— Selecciona equipo —</option>
                {teamList.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-secondary" />
            </div>
          )}

          {viewMode === 'player' && (
            <p className="text-xs text-ink-secondary italic">
              Filtrado por jugador disponible próximamente
            </p>
          )}
        </div>

        {/* Main layout: court + stats */}
        <div className="grid grid-cols-1 lg:grid-cols-[auto_1fr] gap-4">
          {/* Court */}
          <div className="card p-4 flex flex-col items-center gap-2">
            {isLoading ? (
              <div className="w-[450px] h-[420px] flex items-center justify-center">
                <div className="w-8 h-8 border-2 border-accent-400 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <FibaCourtSVG
                zones={selectedTeam ? zones : []}
                onZoneClick={setHighlightZone}
                highlightZone={highlightZone}
              />
            )}
            {/* Legend */}
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
          </div>

          {/* Zone table */}
          <div className="card p-0 overflow-hidden">
            <div className="p-3 border-b border-surface-border">
              <p className="text-sm font-medium text-ink-primary">Estadísticas por Zona</p>
              {totalFga > 0 && (
                <p className="text-xs text-ink-secondary mt-0.5">
                  Total: {totalFgm}/{totalFga} ({(totalFgm / totalFga * 100).toFixed(1)}%)
                </p>
              )}
            </div>
            {!selectedTeam ? (
              <div className="p-8 text-center text-ink-secondary text-sm">
                Selecciona un equipo para ver estadísticas por zona
              </div>
            ) : isLoading ? (
              <div className="p-8 flex justify-center">
                <div className="w-6 h-6 border-2 border-accent-400 border-t-transparent rounded-full animate-spin" />
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
    </PageTransition>
  )
}
