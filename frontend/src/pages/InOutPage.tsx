/**
 * InOutPage — Fase 4
 * Impacto de jugadores dentro/fuera de la cancha con cards ON/OFF.
 */
import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftRight, Users } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import {
  getPlayerStats,
  getTeamStats,
  getInOutAnalysis,
  type InOutStatBlock,
  type PlayerStat,
} from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'

// -- Helpers ------------------------------------------------------------------

function delta(a: number | undefined, b: number | undefined): number {
  return (a ?? 0) - (b ?? 0)
}

function DeltaBar({ value, label }: { value: number; label: string }) {
  const pct = Math.min(Math.abs(value) * 5, 100)
  const color = value >= 0 ? 'bg-emerald-500' : 'bg-red-500'
  const sign  = value >= 0 ? '+' : ''
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-ink-secondary">{label}</span>
      <div className="flex items-center gap-2">
        <div className="flex-1 h-2 bg-surface-hover rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
        </div>
        <span className={`text-xs font-mono font-semibold w-12 text-right ${value >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {sign}{value.toFixed(1)}
        </span>
      </div>
    </div>
  )
}

function fmt(v: number | undefined, dec = 1): string {
  return v != null ? v.toFixed(dec) : '—'
}

function StatRow({ label, val }: { label: string; val: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-ink-secondary">{label}</span>
      <span className="font-mono text-ink-primary">{val}</span>
    </div>
  )
}

function StatCard({ label, block, accent }: { label: string; block: InOutStatBlock; accent: string }) {
  const nr = block.net_rating ?? 0
  return (
    <div className={`card p-4 flex-1 border-t-2 ${accent} space-y-3`}>
      <h3 className="text-sm font-semibold text-ink-primary">{label}</h3>

      {/* Ratings */}
      <div>
        <p className="text-xs font-semibold text-ink-secondary uppercase tracking-wide mb-1">Rating</p>
        <div className="space-y-0.5">
          <div className="flex justify-between text-sm">
            <span className="text-ink-secondary">Net Rating</span>
            <span className={`font-mono font-semibold ${nr >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {nr >= 0 ? '+' : ''}{fmt(block.net_rating)}
            </span>
          </div>
          <StatRow label="ORtg" val={fmt(block.offensive_rating)} />
          <StatRow label="DRtg" val={fmt(block.defensive_rating)} />
          <StatRow label="Poss/40min" val={fmt(block.possessions_per_40)} />
        </div>
      </div>

      {/* Shooting */}
      <div>
        <p className="text-xs font-semibold text-ink-secondary uppercase tracking-wide mb-1">Tiro</p>
        <div className="space-y-0.5">
          <StatRow label="Pts a favor"  val={fmt(block.points_for)} />
          <StatRow label="Pts en contra" val={fmt(block.points_against)} />
          <StatRow label="eFG%"  val={`${fmt(block.efg_percentage)}%`} />
          <StatRow label="TS%"   val={`${fmt(block.true_shooting)}%`} />
          <StatRow label="T2"    val={`${block.fg2_made ?? '—'}/${block.fg2_attempts ?? '—'} (${fmt(block.fg2_percentage)}%)`} />
          <StatRow label="T3"    val={`${block.fg3_made ?? '—'}/${block.fg3_attempts ?? '—'} (${fmt(block.fg3_percentage)}%)`} />
          <StatRow label="TL"    val={`${block.ft_made ?? '—'}/${block.ft_attempts ?? '—'} (${fmt(block.ft_percentage)}%)`} />
          <StatRow label="3Pr"   val={`${fmt(block.three_point_rate)}%`} />
          <StatRow label="FTr"   val={`${fmt(block.free_throw_rate)}%`} />
        </div>
      </div>

      {/* Rebounding */}
      <div>
        <p className="text-xs font-semibold text-ink-secondary uppercase tracking-wide mb-1">Rebotes</p>
        <div className="space-y-0.5">
          <StatRow label="OR%"  val={`${fmt(block.offensive_rebound_rate)}%`} />
          <StatRow label="DR%"  val={`${fmt(block.defensive_rebound_rate)}%`} />
          <StatRow label="REB-O" val={String(block.off_rebounds ?? '—')} />
          <StatRow label="REB-D" val={String(block.def_rebounds ?? '—')} />
        </div>
      </div>

      {/* Other */}
      <div>
        <p className="text-xs font-semibold text-ink-secondary uppercase tracking-wide mb-1">Otros</p>
        <div className="space-y-0.5">
          <StatRow label="%AST"  val={`${fmt(block.assist_rate)}%`} />
          <StatRow label="%TO"   val={`${fmt(block.turnover_rate)}%`} />
          <StatRow label="AST"   val={String(block.assists ?? '—')} />
          <StatRow label="TOV"   val={String(block.turnovers ?? '—')} />
          <StatRow label="STL"   val={String(block.steals ?? '—')} />
          <StatRow label="BLK"   val={String(block.blocks ?? '—')} />
          <StatRow label="Minutos" val={fmt(block.minutes, 0)} />
        </div>
      </div>
    </div>
  )
}

type TeamOption = { id: string; name: string }

function PlayerSelect({
  label, value, onChange, players, teams: teamsProp,
}: { label: string; value: string; onChange: (v: string) => void; players: PlayerStat[]; teams?: TeamOption[] }) {
  const [nameFilter, setNameFilter] = useState('')
  const [teamFilter, setTeamFilter] = useState('')

  // Derive {id, name} pairs from the loaded players when no independent list is available
  const derivedTeams = useMemo((): TeamOption[] => {
    const map = new Map<string, string>()
    for (const p of players) {
      const id = String(p.team_id ?? '')
      const name = (p.team_name ?? '').trim()
      if (id && name) map.set(id, name)
    }
    return Array.from(map.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [players])

  // Prefer independent team list (from getTeamStats) to decouple dropdown
  // availability from full player load
  const teams = teamsProp && teamsProp.length > 0 ? teamsProp : derivedTeams

  const filtered = useMemo(
    () => players.filter(p => {
      // Use team_id for stable matching — team names can change during the season
      const matchesTeam = teamFilter === '' || String(p.team_id ?? '') === teamFilter
      const matchesName = nameFilter === '' || p.player_name.toLowerCase().includes(nameFilter.toLowerCase())
      return matchesTeam && matchesName
    }),
    [players, teamFilter, nameFilter],
  )

  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs text-ink-secondary font-medium uppercase tracking-wide">{label}</label>
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Buscar nombre…"
          value={nameFilter}
          onChange={e => setNameFilter(e.target.value)}
          className="flex-1 bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-primary placeholder-ink-muted focus:outline-none focus:ring-2 focus:ring-accent-400"
        />
        <select
          value={teamFilter}
          onChange={e => setTeamFilter(e.target.value)}
          className="bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400"
        >
          <option value="">Todos los equipos</option>
          {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400">
        <option value="">— Selecciona jugador —</option>
        {filtered.map((p, idx) => (
          <option key={`${p.player_id}_${(p.team_name ?? '').trim()}_${idx}`} value={p.player_id}>
            {p.player_name} ({(p.team_name ?? '').trim() || '—'})
          </option>
        ))}
      </select>
    </div>
  )
}

// -- Component ----------------------------------------------------------------

const TABS = ['IN/OUT', 'IN vs IN'] as const

export default function InOutPage() {
  const { collection } = useCollection()
  const [tab, setTab]       = useState<typeof TABS[number]>('IN/OUT')
  const [p1, setP1]         = useState('')
  const [together1, setT1]  = useState('')
  const [together2, setT2]  = useState('')

  const { data: players = [] } = useQuery<PlayerStat[]>({
    queryKey: ['player-list', collection?.name],
    queryFn:  () => getPlayerStats(collection!.name),
    enabled:  Boolean(collection),
    staleTime: 5 * 60_000,
    select: rows => [...rows].sort((a, b) => a.player_name.localeCompare(b.player_name)),
  })

  // Independent team list — available before player data loads; use team_id for stable matching
  const { data: teamList = [] } = useQuery<TeamOption[]>({
    queryKey: ['team-list-lineups', collection?.name],
    queryFn:  () => getTeamStats(collection!.name).then(d =>
      (d.team_stats ?? [])
        .filter(t => t.team_id != null)
        .map(t => ({ id: String(t.team_id), name: t.team_name }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    ),
    enabled:  Boolean(collection),
    staleTime: 10 * 60_000,
  })

  const { data: inout, isFetching: inoutLoading } = useQuery({
    queryKey: ['inout', collection?.name, p1],
    queryFn:  () => getInOutAnalysis(collection!.name, p1),
    enabled:  Boolean(collection) && Boolean(p1),
  })

  // IN vs IN: independent ON-court queries for each player
  const { data: inout1, isFetching: inout1Loading } = useQuery({
    queryKey: ['inout', collection?.name, together1],
    queryFn:  () => getInOutAnalysis(collection!.name, together1),
    enabled:  Boolean(collection) && Boolean(together1),
  })
  const { data: inout2, isFetching: inout2Loading } = useQuery({
    queryKey: ['inout', collection?.name, together2],
    queryFn:  () => getInOutAnalysis(collection!.name, together2),
    enabled:  Boolean(collection) && Boolean(together2),
  })

  return (
    <PageTransition>
      <div className="space-y-4">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Análisis IN/OUT</h1>
          <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-surface-border">
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? 'border-accent-500 text-accent-400'
                  : 'border-transparent text-ink-secondary hover:text-ink-primary'
              }`}>
              {t}
            </button>
          ))}
        </div>

        {/* IN/OUT Tab */}
        {tab === 'IN/OUT' && (
          <div className="space-y-4">
            <div className="card p-4 max-w-xl">
              <PlayerSelect key={collection?.name ?? ''} label="Jugador" value={p1} onChange={setP1} players={players} teams={teamList} />
            </div>

            {inoutLoading && (
              <div className="text-sm text-ink-secondary animate-pulse">Calculando impacto…</div>
            )}

            {inout && !inoutLoading && (
              <>
                <div className="flex items-center gap-2">
                  <ArrowLeftRight className="w-4 h-4 text-accent-400" />
                  <span className="text-sm font-medium text-ink-primary">{inout.player_name}</span>
                  <span className="text-xs text-ink-secondary">— {inout.team_name}</span>
                </div>

                {/* ON/OFF cards */}
                <div className="flex gap-3">
                  <StatCard label="🟢 En cancha (ON)" block={inout.on} accent="border-emerald-500" />
                  <StatCard label="🔴 Fuera (OFF)"    block={inout.off} accent="border-red-500" />
                </div>

                {/* Deltas */}
                <div className="card p-4">
                  <h3 className="text-xs font-semibold text-ink-secondary uppercase tracking-wide mb-3">
                    Impacto diferencial (ON − OFF)
                  </h3>
                  <div className="space-y-2">
                    <DeltaBar value={delta(inout.on.net_rating, inout.off.net_rating)} label="Net Rating" />
                    <DeltaBar value={delta(inout.on.offensive_rating, inout.off.offensive_rating)} label="ORtg" />
                    <DeltaBar value={delta(inout.off.defensive_rating, inout.on.defensive_rating)} label="DRtg (↓ mejor)" />
                    <DeltaBar value={delta(inout.on.efg_percentage, inout.off.efg_percentage)} label="eFG%" />
                    <DeltaBar value={delta(inout.on.true_shooting, inout.off.true_shooting)} label="TS%" />
                    <DeltaBar value={delta(inout.on.offensive_rebound_rate, inout.off.offensive_rebound_rate)} label="OR%" />
                    <DeltaBar value={delta(inout.on.defensive_rebound_rate, inout.off.defensive_rebound_rate)} label="DR%" />
                    <DeltaBar value={delta(inout.off.turnover_rate, inout.on.turnover_rate)} label="%TO (↓ mejor)" />
                  </div>
                </div>
              </>
            )}

            {!p1 && (
              <div className="card p-10 flex flex-col items-center gap-2 text-center">
                <ArrowLeftRight className="w-8 h-8 text-brand-400 opacity-40" />
                <p className="text-ink-secondary text-sm">Selecciona un jugador para ver su impacto IN/OUT.</p>
              </div>
            )}
          </div>
        )}

        {/* IN vs IN Tab */}
        {tab === 'IN vs IN' && (
          <div className="space-y-4">
            <div className="card p-4 grid grid-cols-2 gap-4 max-w-3xl">
              <PlayerSelect key={`${collection?.name ?? ''}_1`} label="Jugador 1" value={together1} onChange={(v) => setT1(v)} players={players} teams={teamList} />
              <PlayerSelect key={`${collection?.name ?? ''}_2`} label="Jugador 2" value={together2} onChange={(v) => setT2(v)} players={players.filter(p => p.player_id !== together1)} teams={teamList} />
            </div>

            {(inout1Loading || inout2Loading) && (
              <div className="text-sm text-ink-secondary animate-pulse">Calculando impacto…</div>
            )}

            {inout1 && inout2 && !inout1Loading && !inout2Loading && (
              <>
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-accent-400" />
                  <span className="text-sm font-medium text-ink-primary">{inout1.player_name}</span>
                  <span className="text-xs text-ink-secondary">vs</span>
                  <span className="text-sm font-medium text-ink-primary">{inout2.player_name}</span>
                  <span className="text-xs text-ink-secondary">— Impacto en pista (ON)</span>
                </div>

                {/* ON cards side by side */}
                <div className="flex gap-3">
                  <StatCard label={`🟢 ${inout1.player_name} (ON)`} block={inout1.on} accent="border-accent-500" />
                  <StatCard label={`🟢 ${inout2.player_name} (ON)`} block={inout2.on} accent="border-brand-500" />
                </div>

                {/* Differential P1 ON − P2 ON */}
                <div className="card p-4">
                  <h3 className="text-xs font-semibold text-ink-secondary uppercase tracking-wide mb-3">
                    Impacto diferencial ({inout1.player_name} − {inout2.player_name})
                  </h3>
                  <div className="space-y-2">
                    <DeltaBar value={delta(inout1.on.net_rating,            inout2.on.net_rating)}            label="Net Rating" />
                    <DeltaBar value={delta(inout1.on.offensive_rating,      inout2.on.offensive_rating)}      label="ORtg" />
                    <DeltaBar value={delta(inout2.on.defensive_rating,      inout1.on.defensive_rating)}      label="DRtg (↓ mejor)" />
                    <DeltaBar value={delta(inout1.on.efg_percentage,        inout2.on.efg_percentage)}        label="eFG%" />
                    <DeltaBar value={delta(inout1.on.true_shooting,         inout2.on.true_shooting)}         label="TS%" />
                    <DeltaBar value={delta(inout1.on.offensive_rebound_rate,inout2.on.offensive_rebound_rate)} label="OR%" />
                    <DeltaBar value={delta(inout1.on.defensive_rebound_rate,inout2.on.defensive_rebound_rate)} label="DR%" />
                  </div>
                </div>
              </>
            )}

            {/* Partial load: one player selected */}
            {inout1 && !inout2 && !inout1Loading && together2 === '' && (
              <>
                <div className="flex items-center gap-2">
                  <ArrowLeftRight className="w-4 h-4 text-accent-400" />
                  <span className="text-sm font-medium text-ink-primary">{inout1.player_name} (ON)</span>
                </div>
                <div className="flex gap-3">
                  <StatCard label={`🟢 ${inout1.player_name} (ON)`} block={inout1.on} accent="border-accent-500" />
                </div>
              </>
            )}

            {(!together1 && !together2) && (
              <div className="card p-10 flex flex-col items-center gap-2 text-center">
                <Users className="w-8 h-8 text-brand-400 opacity-40" />
                <p className="text-ink-secondary text-sm">Selecciona dos jugadores para comparar su impacto en pista (ON).</p>
              </div>
            )}
          </div>
        )}
      </div>
    </PageTransition>
  )
}
