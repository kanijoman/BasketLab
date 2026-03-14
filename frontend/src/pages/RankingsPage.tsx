/**
 * RankingsPage — player stat leaderboards.
 *
 * Select a stat category ? see ranked list with bar fills.
 * Filters: min minutes, team.
 * Top 3 highlighted with medal styling.
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getPlayerStats, type PlayerStat } from '@/api/client'
import { fmt, fmtPct } from '@/lib/utils'
import PageTransition from '@/components/ui/PageTransition'

// -- Stat definitions ----------------------------------------------------------

interface StatDef {
  key: keyof PlayerStat
  label: string
  format: (v: number | undefined) => string
  reverse?: boolean   // lower = better
}

const STAT_TABS: StatDef[] = [
  { key: 'points_per_game',    label: 'Puntos',      format: v => fmt(v) },
  { key: 'rebounds_per_game',  label: 'Rebotes',     format: v => fmt(v) },
  { key: 'assists_per_game',   label: 'Asistencias', format: v => fmt(v) },
  { key: 'steals_per_game',    label: 'Robos',       format: v => fmt(v) },
  { key: 'blocks_per_game',    label: 'Tapones',     format: v => fmt(v) },
  { key: 'valoracion_per_game',label: 'Valoración',  format: v => fmt(v) },
  { key: 'fg2_percentage',     label: '% T2',        format: v => fmtPct(v) },
  { key: 'fg3_percentage',     label: '% T3',        format: v => fmtPct(v) },
  { key: 'turnovers_per_game', label: 'Pérdidas',    format: v => fmt(v), reverse: true },
]

// -- Medal helpers -------------------------------------------------------------

const MEDAL: Record<number, { emoji: string; bg: string; text: string }> = {
  1: { emoji: '??', bg: 'bg-yellow-900/30', text: 'text-yellow-400' },
  2: { emoji: '??', bg: 'bg-slate-700/40',  text: 'text-slate-300'  },
  3: { emoji: '??', bg: 'bg-amber-900/30',  text: 'text-amber-500'  },
}

// -- Component -----------------------------------------------------------------

export default function RankingsPage() {
  const { collection } = useCollection()
  const [statIdx, setStatIdx]     = useState(0)
  const [minMin, setMinMin]       = useState(0)
  const [teamFilter, setTeamFilter] = useState('')

  const { data: rawPlayers = [], isLoading } = useQuery({
    queryKey: ['player-stats', collection?.name],
    queryFn:  () => getPlayerStats(collection!.name),
    enabled:  Boolean(collection),
    staleTime: 5 * 60_000,
  })

  const stat = STAT_TABS[statIdx]

  const teamOptions = useMemo(
    () => [...new Set(rawPlayers.map(p => p.team_name))].sort(),
    [rawPlayers],
  )

  const ranked = useMemo(() => {
    let list = rawPlayers
    if (minMin > 0)    list = list.filter(p => p.minutes_per_game >= minMin)
    if (teamFilter)    list = list.filter(p => p.team_name === teamFilter)
    list = [...list].sort((a, b) => {
      const av = (a[stat.key] as number) ?? 0
      const bv = (b[stat.key] as number) ?? 0
      return stat.reverse ? av - bv : bv - av
    })
    return list
  }, [rawPlayers, stat, minMin, teamFilter])

  const maxVal = useMemo(
    () => Math.max(...ranked.map(p => (p[stat.key] as number) ?? 0), 0.001),
    [ranked, stat],
  )

  if (!collection) {
    return (
      <PageTransition>
        <p className="text-center text-ink-muted mt-16">Selecciona una colección para continuar.</p>
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <div className="space-y-4">

        {/* Header */}
        <div>
          <h1 className="text-xl font-bold text-ink-primary">Rankings de Jugadores</h1>
          <p className="text-sm text-ink-muted mt-0.5">{collection.label}</p>
        </div>

        {/* Stat tabs (scrollable on mobile) */}
        <div className="overflow-x-auto pb-1">
          <div className="flex gap-2 min-w-max">
            {STAT_TABS.map((s, i) => (
              <button
                key={s.key as string}
                onClick={() => setStatIdx(i)}
                className={[
                  'px-3 py-1.5 rounded-full text-xs font-medium transition-colors whitespace-nowrap',
                  i === statIdx
                    ? 'bg-brand-600/30 text-brand-400 border border-brand-600/40'
                    : 'bg-surface-raised text-ink-secondary border border-surface-border hover:text-ink-primary',
                ].join(' ')}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Filters row */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Min minutes */}
          <label className="flex items-center gap-2 text-xs text-ink-muted">
            MIN &ge;
            <input
              type="number"
              min={0}
              max={40}
              step={1}
              value={minMin}
              onChange={e => setMinMin(Number(e.target.value))}
              className="input w-16 py-1 text-xs text-center"
            />
            min/partido
          </label>

          {/* Team filter */}
          <div className="relative">
            <select
              value={teamFilter}
              onChange={e => setTeamFilter(e.target.value)}
              className="select pr-8 pl-3 py-1.5 text-xs appearance-none"
            >
              <option value="">Todos los equipos</option>
              {teamOptions.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-ink-muted pointer-events-none" />
          </div>

          <span className="text-xs text-ink-muted ml-auto">{ranked.length} jugadores</span>
        </div>

        {/* Ranked list */}
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="h-12 rounded-card animate-pulse bg-surface-raised/60" />
            ))}
          </div>
        ) : ranked.length === 0 ? (
          <div className="py-16 text-center text-sm text-ink-muted">
            Sin resultados para los filtros aplicados.
          </div>
        ) : (
          <div className="space-y-1.5">
            {ranked.slice(0, 30).map((player, idx) => {
              const rank   = idx + 1
              const val    = (player[stat.key] as number) ?? 0
              const barPct = maxVal > 0 ? (val / maxVal) * 100 : 0
              const medal  = MEDAL[rank]

              return (
                <div
                  key={player.player_id}
                  className={[
                    'relative flex items-center gap-3 px-4 py-3 rounded-card border overflow-hidden',
                    medal
                      ? `${medal.bg} border-surface-border/60`
                      : 'bg-surface-raised border-surface-border',
                  ].join(' ')}
                >
                  {/* Bar fill */}
                  <div
                    className="absolute inset-y-0 left-0 bg-brand-600/8 pointer-events-none"
                    style={{ width: `${Math.min(barPct, 100)}%` }}
                  />

                  {/* Rank */}
                  <span className={`w-8 shrink-0 text-center font-bold text-sm ${medal ? medal.text : 'text-ink-muted'}`}>
                    {medal ? medal.emoji : rank}
                  </span>

                  {/* Player info */}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm text-ink-primary truncate">{player.player_name}</p>
                    <p className="text-xs text-ink-muted truncate">{player.team_name}</p>
                  </div>

                  {/* Value */}
                  <span className={`shrink-0 text-lg font-bold tabular-nums ${medal ? medal.text : 'text-ink-primary'}`}>
                    {stat.format(val)}
                  </span>
                </div>
              )
            })}
          </div>
        )}

        {ranked.length > 30 && (
          <p className="text-xs text-center text-ink-muted">Mostrando los 30 primeros de {ranked.length}</p>
        )}

      </div>
    </PageTransition>
  )
}
