/** What the tabs of the predictive analysis share: number formats and the season + team picker (issue #193). */
import { useEffect, useState } from 'react'
import { Field, Select } from '@/components/ui/Field'
import { useQuery } from '@tanstack/react-query'
import { getHistoricalSeasons, getHistoricalTeams, type HistoricalTeamEntry } from '@/api/client'

export const fmt = (v: number | null | undefined, d = 1) =>
  v == null ? '—' : v.toFixed(d)

export const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${(v * 100).toFixed(1)} %`

// ── Season + team of the historical models: the state and the two loads the tabs shared by hand (issue #452) ──
export function useHistoricalPicker() {
  const [seasons, setSeasons] = useState<string[]>([])
  const [teams, setTeams]     = useState<HistoricalTeamEntry[]>([])
  const [season, setSeason]   = useState('')
  const [teamId, setTeamId]   = useState('')

  useEffect(() => {
    getHistoricalSeasons().then(s => {
      setSeasons(s)
      if (s.length) setSeason(s[0])
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!season) return
    getHistoricalTeams(season).then(t => {
      setTeams(t)
      if (t.length) setTeamId(t[0].team_id)
    }).catch(() => {})
  }, [season])

  return { seasons, teams, season, setSeason, teamId, setTeamId }
}

/** The two selects of that state. */
export function HistoricalFields({ picker: { seasons, teams, season, setSeason, teamId, setTeamId } }: { picker: ReturnType<typeof useHistoricalPicker> }) {
  return (
    <>
      <Field label="Temporada" className="w-40">
        <Select value={season} onChange={e => setSeason(e.target.value)}>
          {seasons.map(s => <option key={s} value={s}>{s}</option>)}
        </Select>
      </Field>
      <Field label="Equipo" className="w-56">
        <Select value={teamId} onChange={e => setTeamId(e.target.value)}>
          {teams.map(t => <option key={t.team_id} value={t.team_id}>{t.team_name}</option>)}
        </Select>
      </Field>
    </>
  )
}

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
