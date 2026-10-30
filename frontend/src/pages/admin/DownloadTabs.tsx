/** Tabs "Descargar FEB" and "Descargar FBCYL": cascading selects and the scraping of a competition with its progress (issue #195). */
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import {
  getFebCompetitions, getFebSeasons, getFebGroups,
  getFbcylInit, getFbcylCategories, getFbcylCompetitions, postScrapeStart,
} from '@/api/client'
import Button from '@/components/ui/Button'
import { ProgressPanel } from './ProgressPanels'
import { CascadeSelect, StartError } from './shared'

/** The start button and the progress of the job it starts (the button is replaced by the progress once there is a job). */
function StartJob({ ready, starting, jobId, error, onStart }: { ready: boolean; starting: boolean; jobId: string | null; error: string | null; onStart: () => void }) {
  const queryClient = useQueryClient()
  return (
    <>
      {error && <StartError message={error} />}
      {!jobId && (
        <Button icon={Play} loading={starting} disabled={!ready} onClick={onStart} className="w-full justify-center py-2.5">
          Iniciar descarga
        </Button>
      )}
      {jobId && <ProgressPanel jobId={jobId} onDone={() => queryClient.invalidateQueries({ queryKey: ['collections-list'] })} />}
    </>
  )
}

/** Starts a scraping job and keeps its id, whether it is starting and what failed. */
function useScrapeStart(request: () => Parameters<typeof postScrapeStart>[0]) {
  const [jobId, setJobId] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function start() {
    setStarting(true); setError(null)
    try {
      const { job_id } = await postScrapeStart(request())
      setJobId(job_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar')
    } finally {
      setStarting(false)
    }
  }
  return { jobId, setJobId, starting, error, start }
}

export function FEBDownloadTab() {
  const [compUrl, setCompUrl] = useState(''); const [compLabel, setCompLabel] = useState('')
  const [season,  setSeason]  = useState(''); const [seasonLabel, setSeasonLabel] = useState('')
  const [group,   setGroup]   = useState(''); const [groupLabel, setGroupLabel] = useState('')
  const job = useScrapeStart(() => ({
    league: 'FEB',
    feb: { competition_url: compUrl, season_value: season, group_value: group, competition_label: compLabel, season_label: seasonLabel, group_label: groupLabel },
  }))

  const { data: competitions, isLoading: loadingComps } = useQuery({
    queryKey: ['feb-competitions'], queryFn: getFebCompetitions, staleTime: 5 * 60_000,
  })
  const { data: seasons, isLoading: loadingSeasons } = useQuery({
    queryKey: ['feb-seasons', compUrl], queryFn: () => getFebSeasons(compUrl),
    enabled: !!compUrl, staleTime: 5 * 60_000,
  })
  const { data: groups, isLoading: loadingGroups } = useQuery({
    queryKey: ['feb-groups', compUrl, season], queryFn: () => getFebGroups(compUrl, season),
    enabled: !!compUrl && !!season, staleTime: 0,
  })

  function handleCompChange(url: string) {
    setCompUrl(url); setCompLabel(competitions?.find(c => c.results_url === url)?.name ?? '')
    setSeason(''); setSeasonLabel(''); setGroup(''); setGroupLabel(''); job.setJobId(null)
  }
  function handleSeasonChange(val: string) {
    setSeason(val); setSeasonLabel(seasons?.find(s => s.value === val)?.text ?? val)
    setGroup(''); setGroupLabel(''); job.setJobId(null)
  }
  function handleGroupChange(val: string) {
    setGroup(val); setGroupLabel(groups?.find(g => g.value === val)?.text ?? val); job.setJobId(null)
  }

  return (
    <div className="mt-4 space-y-4">
      <CascadeSelect label="Competición" options={(competitions ?? []).map(c => ({ text: c.name, value: c.results_url }))}
        value={compUrl} onChange={handleCompChange} loading={loadingComps} placeholder="Seleccionar competición…" />
      <CascadeSelect label="Temporada" options={seasons ?? []} value={season} onChange={handleSeasonChange}
        loading={loadingSeasons} disabled={!compUrl} placeholder="Seleccionar temporada…" />
      <CascadeSelect label="Grupo" options={groups ?? []} value={group} onChange={handleGroupChange}
        loading={loadingGroups} disabled={!season} placeholder="Seleccionar grupo…" />
      <StartJob ready={!!compUrl && !!season && !!group} starting={job.starting} jobId={job.jobId} error={job.error} onStart={job.start} />
    </div>
  )
}

export function FBCYLDownloadTab() {
  const [season, setSeason] = useState(''); const [gender, setGender] = useState('')
  const [territory, setTerritory] = useState('0'); const [category, setCategory] = useState('')
  const [compId, setCompId] = useState(''); const [compLabel, setCompLabel] = useState('')
  const job = useScrapeStart(() => ({
    league: 'FBCYL',
    fbcyl: { competition_id: compId, competition_label: compLabel, season, gender, territory, category },
  }))

  const { data: init, isLoading: loadingInit } = useQuery({
    queryKey: ['fbcyl-init'], queryFn: getFbcylInit, staleTime: 5 * 60_000,
  })
  const { data: categories, isLoading: loadingCats } = useQuery({
    queryKey: ['fbcyl-categories', season, gender, territory],
    queryFn: () => getFbcylCategories(season, gender, territory),
    enabled: !!season, staleTime: 5 * 60_000,
  })
  const { data: competitions, isLoading: loadingComps } = useQuery({
    queryKey: ['fbcyl-competitions', category, gender, territory],
    queryFn: () => getFbcylCompetitions(category, gender, territory),
    enabled: !!category, staleTime: 5 * 60_000,
  })

  const reset = () => { setCategory(''); setCompId(''); job.setJobId(null) }
  function handleSeasonChange(v: string)    { setSeason(v);    reset() }
  function handleGenderChange(v: string)    { setGender(v);    reset() }
  function handleTerritoryChange(v: string) { setTerritory(v); reset() }
  function handleCategoryChange(v: string)  { setCategory(v);  setCompId(''); job.setJobId(null) }
  function handleCompChange(v: string) {
    setCompId(v); setCompLabel(competitions?.find(c => c.value === v)?.text ?? v); job.setJobId(null)
  }

  return (
    <div className="mt-4 space-y-4">
      <CascadeSelect label="Temporada"   options={init?.seasons     ?? []} value={season}    onChange={handleSeasonChange}    loading={loadingInit}  placeholder="Seleccionar temporada…" />
      <CascadeSelect label="Género"      options={init?.genders     ?? []} value={gender}    onChange={handleGenderChange}    disabled={!season}     placeholder="Seleccionar género…" />
      <CascadeSelect label="Territorio"  options={init?.territories ?? []} value={territory} onChange={handleTerritoryChange} disabled={!season}     placeholder="Seleccionar territorio…" />
      <CascadeSelect label="Categoría"   options={categories ?? []}        value={category}  onChange={handleCategoryChange}  loading={loadingCats}  disabled={!season}    placeholder="Seleccionar categoría…" />
      <CascadeSelect label="Competición" options={competitions ?? []}       value={compId}    onChange={handleCompChange}      loading={loadingComps} disabled={!category}  placeholder="Seleccionar competición…" />
      <StartJob ready={!!compId && !!season && !!category} starting={job.starting} jobId={job.jobId} error={job.error} onStart={job.start} />
    </div>
  )
}
