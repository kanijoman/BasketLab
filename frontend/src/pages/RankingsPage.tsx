/**
 * RankingsPage — player stat leaderboards.
 *
 * Select a stat category (Básicas / Tiro / Avanzadas) → see ranked list with bar fills.
 * Filters: min minutes, team, player name search.
 * Top 3 global ranks highlighted with medal icons (Trophy/Medal/Award).
 * Filtering by team/player preserves global league rank, not filtered rank.
 * Each row shows the delta relative to the league leader.
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Trophy, Medal, Award, Search } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

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

interface StatGroup {
  label: string
  stats: StatDef[]
}

const STAT_GROUPS: StatGroup[] = [
  {
    label: 'Básicas',
    stats: [
      { key: 'points_per_game',             label: 'Puntos',      format: v => fmt(v) },
      { key: 'rebounds_per_game',           label: 'Rebotes',     format: v => fmt(v) },
      { key: 'offensive_rebounds_per_game', label: 'Reb. Of.',    format: v => fmt(v) },
      { key: 'defensive_rebounds_per_game', label: 'Reb. Def.',   format: v => fmt(v) },
      { key: 'assists_per_game',            label: 'Asistencias', format: v => fmt(v) },
      { key: 'steals_per_game',             label: 'Robos',       format: v => fmt(v) },
      { key: 'blocks_per_game',             label: 'Tapones',     format: v => fmt(v) },
      { key: 'turnovers_per_game',          label: 'Pérdidas',    format: v => fmt(v), reverse: true },
      { key: 'fouls_per_game',              label: 'Faltas',      format: v => fmt(v), reverse: true },
      { key: 'valoracion_per_game',         label: 'Valoración',  format: v => fmt(v) },
      { key: 'pllss_per_game',              label: '+/-',         format: v => fmt(v) },
    ],
  },
  {
    label: 'Tiro',
    stats: [
      { key: 'fg1_percentage',   label: '% TL',  format: v => fmtPct(v) },
      { key: 'fg2_percentage',   label: '% T2',  format: v => fmtPct(v) },
      { key: 'fg3_percentage',   label: '% T3',  format: v => fmtPct(v) },
      { key: 'efg_percentage',   label: 'eFG%',  format: v => fmtPct(v) },
      { key: 'true_shooting',    label: 'TS%',   format: v => fmtPct(v) },
      { key: 'free_throw_rate',  label: 'FTr',   format: v => fmt(v) },
      { key: 'three_point_rate', label: '3PAr',  format: v => fmt(v) },
    ],
  },
  {
    label: 'Avanzadas',
    stats: [
      { key: 'usage_pct',   label: 'USG%',    format: v => fmtPct(v) },
      { key: 'orating',     label: 'ORtg',    format: v => fmt(v) },
      { key: 'drating',     label: 'DRtg',    format: v => fmt(v), reverse: true },
      { key: 'net_rtg',     label: 'Net Rtg', format: v => fmt(v) },
      { key: 'ast_pct',     label: 'Ast%',    format: v => fmtPct(v) },
      { key: 'tov_pct_adv', label: 'TO%',     format: v => fmtPct(v), reverse: true },
      { key: 'stl_pct',     label: 'Stl%',    format: v => fmtPct(v) },
      { key: 'blk_pct',     label: 'Blk%',    format: v => fmtPct(v) },
      { key: 'orb_pct',     label: 'ROF%',    format: v => fmtPct(v) },
      { key: 'drb_pct',     label: 'RDef%',   format: v => fmtPct(v) },
      { key: 'pie',         label: 'PIE',     format: v => fmtPct(v) },
    ],
  },
]

// -- Medal helpers -------------------------------------------------------------

interface MedalDef { icon: LucideIcon; bg: string; text: string }

const MEDAL: Record<number, MedalDef> = {
  1: { icon: Trophy, bg: 'bg-yellow-900/30', text: 'text-yellow-400' },
  2: { icon: Medal,  bg: 'bg-slate-700/40',  text: 'text-slate-300'  },
  3: { icon: Award,  bg: 'bg-amber-900/30',  text: 'text-amber-500'  },
}

// -- Component -----------------------------------------------------------------

export default function RankingsPage() {
  const { collection } = useCollection()
  const [groupIdx, setGroupIdx]         = useState(0)
  const [statIdx, setStatIdx]           = useState(0)
  const [minMin, setMinMin]             = useState(0)
  const [teamFilter, setTeamFilter]     = useState('')
  const [playerSearch, setPlayerSearch] = useState('')

  const { data: rawPlayers = [], isLoading } = useQuery({
    queryKey: ['player-stats', collection?.name],
    queryFn:  () => getPlayerStats(collection!.name),
    enabled:  Boolean(collection),
    staleTime: 5 * 60_000,
  })

  const group       = STAT_GROUPS[groupIdx]
  // Clamp so changing group never leaves statIdx out-of-range
  const safeStatIdx = Math.min(statIdx, group.stats.length - 1)
  const stat        = group.stats[safeStatIdx]

  const teamOptions = useMemo(
    () => [...new Set(rawPlayers.map(p => p.team_name))].sort(),
    [rawPlayers],
  )

  // Global ranking: only min-minutes filter, NO team/player filter → real league position
  const allRanked = useMemo(() => {
    let list = rawPlayers
    if (minMin > 0) list = list.filter(p => p.minutes_per_game >= minMin)
    return [...list].sort((a, b) => {
      const av = (a[stat.key] as number) ?? 0
      const bv = (b[stat.key] as number) ?? 0
      return stat.reverse ? av - bv : bv - av
    })
  }, [rawPlayers, stat, minMin])

  // Map player_id → globally-ranked position (1-indexed)
  const globalRankMap = useMemo(
    () => new Map(allRanked.map((p, i) => [p.player_id, i + 1])),
    [allRanked],
  )

  // Visible subset after team + player search filters (rank stays global)
  const filteredRanked = useMemo(() => {
    let list = allRanked
    if (teamFilter)   list = list.filter(p => p.team_name === teamFilter)
    if (playerSearch) list = list.filter(p =>
      p.player_name.toLowerCase().includes(playerSearch.toLowerCase()),
    )
    return list
  }, [allRanked, teamFilter, playerSearch])

  const leaderVal = allRanked.length > 0 ? ((allRanked[0][stat.key] as number) ?? 0) : 0
  const maxVal    = Math.max(...allRanked.map(p => (p[stat.key] as number) ?? 0), 0.001)

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

        {/* Group tabs (Básicas / Tiro / Avanzadas) */}
        <div className="flex gap-2">
          {STAT_GROUPS.map((g, i) => (
            <button
              key={g.label}
              onClick={() => { setGroupIdx(i); setStatIdx(0) }}
              className={[
                'px-3 py-1.5 rounded-full text-xs font-semibold transition-colors',
                i === groupIdx
                  ? 'bg-brand-600/40 text-brand-300 border border-brand-500/50'
                  : 'bg-surface-raised text-ink-secondary border border-surface-border hover:text-ink-primary',
              ].join(' ')}
            >
              {g.label}
            </button>
          ))}
        </div>

        {/* Stat tabs within the active group (scrollable on mobile) */}
        <div className="overflow-x-auto pb-1">
          <div className="flex gap-2 min-w-max">
            {group.stats.map((s, i) => (
              <button
                key={s.key as string}
                onClick={() => setStatIdx(i)}
                className={[
                  'px-3 py-1.5 rounded-full text-xs font-medium transition-colors whitespace-nowrap',
                  i === safeStatIdx
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

          {/* Player search */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-ink-muted pointer-events-none" />
            <input
              type="text"
              placeholder="Buscar jugador…"
              value={playerSearch}
              onChange={e => setPlayerSearch(e.target.value)}
              className="input pl-7 pr-3 py-1.5 text-xs w-44"
            />
          </div>

          <span className="text-xs text-ink-muted ml-auto">{filteredRanked.length} jugadores</span>
        </div>

        {/* Ranked list */}
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="h-12 rounded-card animate-pulse bg-surface-raised/60" />
            ))}
          </div>
        ) : filteredRanked.length === 0 ? (
          <div className="py-16 text-center text-sm text-ink-muted">
            Sin resultados para los filtros aplicados.
          </div>
        ) : (
          <div className="space-y-1.5">
            {filteredRanked.slice(0, 30).map((player, idx) => {
              // Composite key: player_id may be empty/null for some entries — fall back to
              // name+team to avoid React key collisions that cause DOM nodes to persist.
              const rowKey    = player.player_id
                ? player.player_id
                : `${player.player_name}__${player.team_name}__${idx}`
              const rank      = globalRankMap.get(player.player_id) ?? 0
              const val       = (player[stat.key] as number) ?? 0
              const barPct    = maxVal > 0 ? (val / maxVal) * 100 : 0
              const medal     = MEDAL[rank]
              const MedalIcon = medal?.icon
              const rawDelta  = stat.reverse ? val - leaderVal : leaderVal - val
              const deltaStr  = rank === 1 ? '—' : `-${fmt(Math.abs(rawDelta))}`

              return (
                <div
                  key={rowKey}
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

                  {/* Rank / medal icon */}
                  <span className={`w-8 shrink-0 flex items-center justify-center font-bold text-sm ${medal ? medal.text : 'text-ink-muted'}`}>
                    {MedalIcon ? <MedalIcon className="w-5 h-5" /> : rank}
                  </span>

                  {/* Player info */}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm text-ink-primary truncate">{player.player_name}</p>
                    <p className="text-xs text-ink-muted truncate">{player.team_name}</p>
                  </div>

                  {/* Value + delta vs league leader */}
                  <div className="shrink-0 text-right">
                    <span className={`block text-lg font-bold tabular-nums leading-tight ${medal ? medal.text : 'text-ink-primary'}`}>
                      {stat.format(val)}
                    </span>
                    <span className={`block text-xs tabular-nums font-medium ${rank === 1 ? 'text-ink-muted' : 'text-ink-secondary'}`}>
                      {deltaStr}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {filteredRanked.length > 30 && (
          <p className="text-xs text-center text-ink-muted">Mostrando los 30 primeros de {filteredRanked.length}</p>
        )}

      </div>
    </PageTransition>
  )
}

