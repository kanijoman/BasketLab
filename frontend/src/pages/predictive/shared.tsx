/** What the tabs of the predictive analysis share: number formats and the season + team picker (issue #193). */
import { useEffect } from 'react'
import { Field, Select } from '@/components/ui/Field'
import { useQuery } from '@tanstack/react-query'
import { getHistoricalSeasons, getHistoricalTeams, type HistoricalTeamEntry } from '@/api/client'

export const fmt = (v: number | null | undefined, d = 1) =>
  v == null ? '—' : v.toFixed(d)

export const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${(v * 100).toFixed(1)} %`

// ── Shared season + team picker ───────────────────────────────────────────────
export function TeamPicker({
  season, teamId,
  onSeasonChange, onTeamChange,
}: {
  season: string
  teamId: string
  onSeasonChange: (s: string) => void
  onTeamChange:   (id: string) => void
}) {
  const { data: seasons = [], isLoading: loadingSeasons } = useQuery({
    queryKey: ['historical-seasons'],
    queryFn:  getHistoricalSeasons,
    staleTime: 60_000,
  })
  const { data: teams = [], isLoading: loadingTeams } = useQuery({
    queryKey: ['historical-teams', season],
    queryFn:  () => getHistoricalTeams(season || undefined),
    enabled:  true,
    staleTime: 60_000,
  })

  // auto-select first season
  useEffect(() => {
    if (!season && seasons.length > 0) onSeasonChange(seasons[0])
  }, [seasons, season, onSeasonChange])

  // clear team when season changes
  useEffect(() => { onTeamChange('') }, [season, onTeamChange])

  return (
    <div className="flex gap-3 flex-wrap items-end">
      {loadingSeasons || seasons.length === 0 ? (
        <Waiting label="Temporada" loading={loadingSeasons} empty="Sin datos en HISTORICAL" width="w-28" />
      ) : (
        <Field label="Temporada" className="w-32">
          <Select value={season} onChange={e => onSeasonChange(e.target.value)} options={seasons.map(s => ({ value: s, label: s }))} />
        </Field>
      )}
      {loadingTeams || teams.length === 0 ? (
        <Waiting label="Equipo" loading={loadingTeams} empty="Sin equipos para esta temporada" width="w-52" />
      ) : (
        <Field label="Equipo" className="w-56">
          <Select value={teamId} onChange={e => onTeamChange(e.target.value)}
            options={[{ value: '', label: 'Seleccionar equipo…' }, ...(teams as HistoricalTeamEntry[]).map(t => ({ value: t.team_id, label: t.team_name }))]} />
        </Field>
      )}
    </div>
  )
}

/** The place of a control whose options are not there yet (a skeleton) or never will be (what is missing). */
export function Waiting({ label, loading, empty, width = 'w-52' }: { label: string; loading: boolean; empty: string; width?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-ink-muted">{label}</span>
      {loading ? <div className={`h-8 ${width} rounded bg-surface-raised animate-pulse`} /> : <p className="text-xs text-ink-muted italic">{empty}</p>}
    </div>
  )
}
