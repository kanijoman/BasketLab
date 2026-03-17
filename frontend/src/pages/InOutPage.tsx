/**
 * InOutPage — Fase 4
 * Impacto de jugadores dentro/fuera de la cancha con cards ON/OFF.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftRight, Users } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import {
  getPlayerStats,
  getInOutAnalysis,
  getPlayersTogether,
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

function StatCard({ label, block, accent }: { label: string; block: InOutStatBlock; accent: string }) {
  return (
    <div className={`card p-4 flex-1 border-t-2 ${accent}`}>
      <h3 className="text-sm font-semibold text-ink-primary mb-3">{label}</h3>
      <div className="space-y-1.5 text-sm">
        <div className="flex justify-between"><span className="text-ink-secondary">Pts a favor</span><span className="font-mono text-ink-primary">{block.points_for?.toFixed(1) ?? '—'}</span></div>
        <div className="flex justify-between"><span className="text-ink-secondary">Pts en contra</span><span className="font-mono text-ink-primary">{block.points_against?.toFixed(1) ?? '—'}</span></div>
        <div className="flex justify-between"><span className="text-ink-secondary">Net Rating</span>
          <span className={`font-mono font-semibold ${(block.net_rating ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {block.net_rating != null ? (block.net_rating >= 0 ? '+' : '') + block.net_rating.toFixed(1) : '—'}
          </span>
        </div>
        <div className="flex justify-between"><span className="text-ink-secondary">Minutos</span><span className="font-mono text-ink-primary">{block.minutes?.toFixed(0) ?? '—'}</span></div>
      </div>
    </div>
  )
}

function PlayerSelect({
  label, value, onChange, players,
}: { label: string; value: string; onChange: (v: string) => void; players: PlayerStat[] }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-ink-secondary font-medium uppercase tracking-wide">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400">
        <option value="">— Selecciona jugador —</option>
        {players.map(p => (
          <option key={p.player_id} value={p.player_id}>
            {p.player_name} ({p.team_name})
          </option>
        ))}
      </select>
    </div>
  )
}

// -- Component ----------------------------------------------------------------

const TABS = ['IN/OUT', 'Juntos'] as const

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

  const { data: inout, isFetching: inoutLoading } = useQuery({
    queryKey: ['inout', collection?.name, p1],
    queryFn:  () => getInOutAnalysis(collection!.name, p1),
    enabled:  Boolean(collection) && Boolean(p1),
  })

  const { data: tog, isFetching: togLoading } = useQuery({
    queryKey: ['together', collection?.name, together1, together2],
    queryFn:  () => getPlayersTogether(collection!.name, together1, together2),
    enabled:  Boolean(collection) && Boolean(together1) && Boolean(together2),
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
            <div className="card p-4 max-w-md">
              <PlayerSelect label="Jugador" value={p1} onChange={setP1} players={players} />
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
                    <DeltaBar value={delta(inout.on.points_for, inout.off.points_for)} label="Puntos a favor" />
                    <DeltaBar value={delta(inout.off.points_against, inout.on.points_against)} label="Def. (↓ mejor)" />
                    <DeltaBar value={delta(inout.on.net_rating, inout.off.net_rating)} label="Net Rating" />
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

        {/* Juntos Tab */}
        {tab === 'Juntos' && (
          <div className="space-y-4">
            <div className="card p-4 grid grid-cols-2 gap-3 max-w-lg">
              <PlayerSelect label="Jugador 1" value={together1} onChange={(v) => setT1(v)} players={players} />
              <PlayerSelect label="Jugador 2" value={together2} onChange={(v) => setT2(v)} players={players.filter(p => p.player_id !== together1)} />
            </div>

            {togLoading && (
              <div className="text-sm text-ink-secondary animate-pulse">Calculando…</div>
            )}

            {tog && !togLoading && (
              <>
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-accent-400" />
                  <span className="text-xs text-ink-secondary">Estadísticas del equipo</span>
                </div>
                <div className="flex gap-3">
                  <StatCard label="Juntos en cancha" block={tog.together} accent="border-accent-500" />
                  <StatCard label="Al menos uno fuera" block={tog.apart}   accent="border-surface-border" />
                </div>
                <div className="card p-4">
                  <h3 className="text-xs font-semibold text-ink-secondary uppercase tracking-wide mb-3">
                    Impacto diferencial (Juntos − Separados)
                  </h3>
                  <div className="space-y-2">
                    <DeltaBar value={delta(tog.together.points_for, tog.apart.points_for)} label="Puntos a favor" />
                    <DeltaBar value={delta(tog.apart.points_against, tog.together.points_against)} label="Def. (↓ mejor)" />
                    <DeltaBar value={delta(tog.together.net_rating, tog.apart.net_rating)} label="Net Rating" />
                  </div>
                </div>
              </>
            )}

            {(!together1 || !together2) && !tog && (
              <div className="card p-10 flex flex-col items-center gap-2 text-center">
                <Users className="w-8 h-8 text-brand-400 opacity-40" />
                <p className="text-ink-secondary text-sm">Selecciona dos jugadores para comparar su impacto conjunto.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </PageTransition>
  )
}
