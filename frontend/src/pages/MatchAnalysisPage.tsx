/**
 * MatchAnalysisPage — análisis estadístico de un partido concreto.
 *
 * Features:
 * - Selector de partido (lista con marcador y fecha)
 * - Scoreboard (marcador, equipos)
 * - Tabla comparativa con verde/rojo según equipo superior por estadística
 * - Agrupación por secciones (General, Tiro, Cuatro Factores, Avanzadas)
 */
import { useState, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Swords, ChevronDown } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import {
  getMatchList,
  getMatchAnalysis,
  type MatchSummary,
  type ComparisonRow,
} from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'
import ExportButton from '@/components/ui/ExportButton'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtVal(v: number, key: string): string {
  if (v == null) return '—'
  const pctKeys = ['fg_pct', 'two_pct', 'three_pct', 'ft_pct',
                   'efg_pct', 'tov_pct', 'orb_pct']
  if (pctKeys.includes(key)) return `${v.toFixed(1)}%`
  if (key === 'ftr') return v.toFixed(3)
  if (key === 'possessions') return v.toFixed(1)
  if (['oer','der','net_rtg'].includes(key)) return v.toFixed(1)
  return Number.isInteger(v) ? String(v) : v.toFixed(1)
}

const SECTION_ORDER = ['General', 'Tiro', 'Cuatro Factores', 'Posesiones', 'Avanzadas']

function groupBySection(rows: ComparisonRow[]): Array<{ section: string; rows: ComparisonRow[] }> {
  const map = new Map<string, ComparisonRow[]>()
  for (const r of rows) {
    if (!map.has(r.section)) map.set(r.section, [])
    map.get(r.section)!.push(r)
  }
  return SECTION_ORDER
    .filter(s => map.has(s))
    .map(s => ({ section: s, rows: map.get(s)! }))
}

// ---------------------------------------------------------------------------
// Scoreboard
// ---------------------------------------------------------------------------

function Scoreboard({
  home, away, homeScore, awayScore,
}: { home: string; away: string; homeScore: number; awayScore: number }) {
  const homeWins = homeScore > awayScore
  const awayWins = awayScore > homeScore

  return (
    <div className="card p-6 flex items-center justify-between gap-4">
      {/* Home */}
      <div className="flex-1 text-left">
        <p className={`font-bold text-lg leading-tight ${homeWins ? 'text-ink-primary' : 'text-ink-secondary'}`}>
          {home}
        </p>
        <p className="text-xs text-ink-muted mt-0.5">Local</p>
      </div>

      {/* Score */}
      <div className="flex items-center gap-3 shrink-0">
        <span className={`text-4xl font-black tabular-nums ${homeWins ? 'text-ink-primary' : 'text-ink-secondary'}`}>
          {homeScore}
        </span>
        <span className="text-ink-muted font-bold text-xl">–</span>
        <span className={`text-4xl font-black tabular-nums ${awayWins ? 'text-ink-primary' : 'text-ink-secondary'}`}>
          {awayScore}
        </span>
      </div>

      {/* Away */}
      <div className="flex-1 text-right">
        <p className={`font-bold text-lg leading-tight ${awayWins ? 'text-ink-primary' : 'text-ink-secondary'}`}>
          {away}
        </p>
        <p className="text-xs text-ink-muted mt-0.5">Visitante</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Comparison table
// ---------------------------------------------------------------------------

function ComparisonTable({
  rows, homeName, awayName,
}: { rows: ComparisonRow[]; homeName: string; awayName: string }) {
  const sections = groupBySection(rows)

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="grid grid-cols-[1fr_2fr_1fr] gap-0 bg-surface-raised border-b border-surface-border">
        <div className="px-4 py-3 text-sm font-semibold text-ink-primary text-left truncate">{homeName}</div>
        <div className="px-4 py-3 text-xs font-semibold text-ink-muted text-center uppercase tracking-wider">Estadística</div>
        <div className="px-4 py-3 text-sm font-semibold text-ink-primary text-right truncate">{awayName}</div>
      </div>

      {sections.map(({ section, rows: sRows }) => (
        <div key={section}>
          {/* Section header */}
          <div className="px-4 py-1.5 bg-surface-hover/60 border-y border-surface-border/60">
            <span className="text-[10px] font-semibold text-ink-muted uppercase tracking-widest">{section}</span>
          </div>

          {sRows.map(row => {
            const homeWins = row.winner === 'home'
            const awayWins = row.winner === 'away'

            return (
              <div
                key={row.stat_key}
                className="grid grid-cols-[1fr_2fr_1fr] gap-0 border-b border-surface-border/40 last:border-0 hover:bg-surface-hover/30 transition-colors"
              >
                {/* Home value */}
                <div className={`px-4 py-2.5 text-sm tabular-nums font-semibold text-left ${
                  homeWins ? 'text-emerald-400' : awayWins ? 'text-red-400' : 'text-ink-secondary'
                }`}>
                  {homeWins && <span className="mr-1.5 text-[10px]">▶</span>}
                  {fmtVal(row.home_value, row.stat_key)}
                </div>

                {/* Label */}
                <div className="px-4 py-2.5 text-xs text-ink-secondary text-center self-center">
                  {row.label}
                  {row.lower_is_better && (
                    <span className="ml-1 text-ink-muted opacity-60" title="Menor es mejor">↓</span>
                  )}
                </div>

                {/* Away value */}
                <div className={`px-4 py-2.5 text-sm tabular-nums font-semibold text-right ${
                  awayWins ? 'text-emerald-400' : homeWins ? 'text-red-400' : 'text-ink-secondary'
                }`}>
                  {fmtVal(row.away_value, row.stat_key)}
                  {awayWins && <span className="ml-1.5 text-[10px]">◀</span>}
                </div>
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Match selector
// ---------------------------------------------------------------------------

function formatDate(raw: string): string {
  if (!raw) return '—'
  // "DD-MM-YYYY - HH:MM" or ISO or "May 4, 2026 ..."
  const m = raw.match(/(\d{2})-(\d{2})-(\d{4})/)
  if (m) return `${m[1]}/${m[2]}/${m[3]}`
  return raw.split(' - ')[0] ?? raw
}

function TeamFilter({
  teams,
  value,
  onChange,
}: {
  teams: string[]
  value: string
  onChange: (t: string) => void
}) {
  return (
    <div className="relative">
      <select
        className="w-full appearance-none bg-surface-base border border-surface-border rounded-lg
                   px-3 py-2 pr-8 text-sm text-ink-primary
                   focus:outline-none focus:ring-2 focus:ring-brand-500"
        value={value}
        onChange={e => onChange(e.target.value)}
      >
        <option value="">Todos los equipos</option>
        {teams.map(t => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-secondary" />
    </div>
  )
}

function MatchSelector({
  matches,
  selectedId,
  onSelect,
}: {
  matches: MatchSummary[]
  selectedId: string | number | null
  onSelect: (id: string | number) => void
}) {
  return (
    <div className="relative">
      <select
        className="w-full appearance-none bg-surface-base border border-surface-border rounded-lg
                   px-3 py-2 pr-8 text-sm text-ink-primary
                   focus:outline-none focus:ring-2 focus:ring-brand-500"
        value={selectedId ?? ''}
        onChange={e => {
          const raw = e.target.value
          const asNum = Number(raw)
          onSelect(Number.isNaN(asNum) ? raw : asNum)
        }}
      >
        <option value="">— Selecciona un partido —</option>
        {matches.map(m => (
          <option key={String(m.match_id)} value={String(m.match_id)}>
            {formatDate(m.date)}
            {' · '}
            {m.home_team} {m.home_score}–{m.away_score} {m.away_team}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-secondary" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function MatchAnalysisPage() {
  const { collection } = useCollection()
  const [selectedId, setSelectedId] = useState<string | number | null>(null)
  const [teamFilter, setTeamFilter] = useState<string>('')
  const exportRef = useRef<HTMLDivElement>(null)

  const isFbcyl = Boolean(collection?.isFbcyl)

  // Match list
  const { data: matches = [], isLoading: loadingList, isError: errorList } = useQuery({
    queryKey: ['match-list', collection?.name],
    queryFn: () => getMatchList(collection!.name, isFbcyl),
    enabled: Boolean(collection),
    staleTime: 5 * 60_000,
  })

  // Match analysis
  const {
    data: analysis,
    isLoading: loadingAnalysis,
    isError: errorAnalysis,
  } = useQuery({
    queryKey: ['match-analysis', collection?.name, selectedId],
    queryFn: () => getMatchAnalysis(collection!.name, selectedId!, isFbcyl),
    enabled: Boolean(collection && selectedId != null),
    staleTime: 10 * 60_000,
  })

  // Unique sorted team list for the filter dropdown
  const allTeams = [...new Set(matches.flatMap(m => [m.home_team, m.away_team]))].sort()

  // Matches filtered by selected team
  const visibleMatches = teamFilter
    ? matches.filter(m => m.home_team === teamFilter || m.away_team === teamFilter)
    : matches

  const selected = matches.find(m => String(m.match_id) === String(selectedId))

  return (
    <PageTransition>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Swords className="w-5 h-5 text-brand-400 shrink-0" />
            <div>
              <h1 className="text-xl font-bold text-ink-primary">Análisis de Partido</h1>
              <p className="text-xs text-ink-muted mt-0.5">{collection?.label}</p>
            </div>
          </div>
          {analysis && (
            <ExportButton
              filename={`analisis_partido_${selected ? `${selected.home_team}_vs_${selected.away_team}` : selectedId}`}
              csvData={analysis.comparison.map(r => ({ stat: r.label, [analysis.home.team_name]: r.home_value, [analysis.away.team_name]: r.away_value }))}
              csvHeaders={[
                { key: 'stat', label: 'Estadística' },
                { key: analysis.home.team_name, label: analysis.home.team_name },
                { key: analysis.away.team_name, label: analysis.away.team_name },
              ]}
              captureRef={exportRef}
              pdfTitle={selected ? `${selected.home_team} ${selected.home_score}–${selected.away_score} ${selected.away_team}` : 'Análisis de Partido'}
            />
          )}
        </div>

        {/* Collection guard */}
        {!collection && (
          <div className="card p-10 text-center">
            <p className="text-ink-secondary text-sm">Selecciona una colección para continuar.</p>
          </div>
        )}

        {collection && (
          <div className="space-y-4">
            {/* Selector */}
            {loadingList && (
              <div className="h-10 rounded-lg bg-surface-border/40 animate-pulse" />
            )}
            {errorList && (
              <p className="text-sm text-red-400">Error al cargar partidos.</p>
            )}
            {!loadingList && !errorList && (
              <div className="grid grid-cols-[1fr_2fr] gap-2">
                <TeamFilter
                  teams={allTeams}
                  value={teamFilter}
                  onChange={t => {
                    setTeamFilter(t)
                    setSelectedId(null)
                  }}
                />
                <MatchSelector
                  matches={visibleMatches}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
              </div>
            )}

            {/* Meta info */}
            {selected && (
              <p className="text-xs text-ink-muted">
                {selected.venue && <>{selected.venue} · </>}
                {formatDate(selected.date)}
              </p>
            )}

            {/* Loading analysis */}
            {loadingAnalysis && selectedId != null && (
              <div className="space-y-2">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="h-10 rounded bg-surface-border/40 animate-pulse" />
                ))}
              </div>
            )}

            {/* Error */}
            {errorAnalysis && (
              <p className="text-sm text-red-400">Partido no encontrado.</p>
            )}

            {/* Scoreboard + table */}
            {analysis && !loadingAnalysis && (
              <div className="space-y-4" ref={exportRef}>
                <Scoreboard
                  home={analysis.home.team_name}
                  away={analysis.away.team_name}
                  homeScore={analysis.home.pts as number ?? 0}
                  awayScore={analysis.away.pts as number ?? 0}
                />
                <ComparisonTable
                  rows={analysis.comparison}
                  homeName={analysis.home.team_name}
                  awayName={analysis.away.team_name}
                />
              </div>
            )}

            {/* Empty state */}
            {!selectedId && !loadingList && matches.length > 0 && (
              <div className="card p-10 text-center">
                <Swords className="w-8 h-8 text-ink-muted opacity-40 mx-auto mb-2" />
                <p className="text-sm text-ink-secondary">Selecciona un partido para ver el análisis comparativo.</p>
              </div>
            )}

            {!loadingList && matches.length === 0 && (
              <div className="card p-10 text-center">
                <p className="text-sm text-ink-secondary">No hay partidos en esta colección.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </PageTransition>
  )
}
