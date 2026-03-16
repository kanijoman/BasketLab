/**
 * AdminPage — panel de administración de colecciones y descarga de datos.
 *
 * Tab 1 "Colecciones": lista las colecciones disponibles en MongoDB con opción de eliminar.
 * Tab 2 "Descargar FEB": dropdowns en cascada + scraping con barra de progreso.
 * Tab 3 "Descargar FBCYL": ídem para FBCYL.
 */
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Database, Trash2, ExternalLink, RefreshCw,
  ChevronRight, AlertCircle, CheckCircle2, Loader2, Play,
} from 'lucide-react'
import {
  getCollectionList, deleteCollection,
  getFebCompetitions, getFebSeasons, getFebGroups,
  getFbcylInit, getFbcylCategories, getFbcylCompetitions,
  postScrapeStart, getScrapeProgress,
  type CollectionInfo, type DropdownOption, type ScrapeJob,
} from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'

// ── Simple tabs ───────────────────────────────────────────────────────────────

type Tab = 'collections' | 'feb' | 'fbcyl'

const TABS: { id: Tab; label: string }[] = [
  { id: 'collections', label: 'Colecciones' },
  { id: 'feb',         label: 'Descargar FEB' },
  { id: 'fbcyl',       label: 'Descargar FBCYL' },
]

// ── Progress panel ────────────────────────────────────────────────────────────

function ProgressPanel({ jobId, onDone }: { jobId: string; onDone: () => void }) {
  const [job, setJob] = useState<ScrapeJob | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    intervalRef.current = setInterval(async () => {
      try {
        const data = await getScrapeProgress(jobId)
        setJob(data)
        if (data.status === 'done' || data.status === 'error') {
          clearInterval(intervalRef.current!)
          if (data.status === 'done') onDone()
        }
      } catch {
        clearInterval(intervalRef.current!)
      }
    }, 1000)
    return () => clearInterval(intervalRef.current!)
  }, [jobId, onDone])

  if (!job) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-secondary p-4">
        <Loader2 className="w-4 h-4 animate-spin" /> Iniciando descarga…
      </div>
    )
  }

  const pct = job.total > 0 ? Math.round((job.done / job.total) * 100) : 0
  const isDone  = job.status === 'done'
  const isError = job.status === 'error'

  return (
    <div className="space-y-3 p-4 rounded-card border border-surface-border bg-surface-raised">
      <div className="flex items-center gap-2 text-sm">
        {isDone  && <CheckCircle2 className="w-4 h-4 text-up shrink-0" />}
        {isError && <AlertCircle  className="w-4 h-4 text-down shrink-0" />}
        {!isDone && !isError && <Loader2 className="w-4 h-4 animate-spin text-brand-400 shrink-0" />}
        <span className={isDone ? 'text-up' : isError ? 'text-down' : 'text-ink-primary'}>
          {isDone  ? `Descarga completada — ${job.done} partidos` :
           isError ? 'Error durante la descarga' :
                     `Descargando… ${job.done} / ${job.total ?? '?'}`}
        </span>
        {job.collection && (
          <span className="ml-auto text-xs text-ink-muted font-mono truncate max-w-[14rem]">
            {job.collection}
          </span>
        )}
      </div>
      {!isError && (
        <div className="h-2 rounded-full bg-surface-border overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${isDone ? 'bg-up' : 'bg-brand-500'}`}
            style={{ width: isDone ? '100%' : `${pct}%` }}
          />
        </div>
      )}
      {job.current_match && !isDone && (
        <p className="text-xs text-ink-muted font-mono truncate">Partido: {job.current_match}</p>
      )}
      {job.errors.length > 0 && (
        <details className="text-xs">
          <summary className="text-down cursor-pointer">
            {job.errors.length} error{job.errors.length > 1 ? 'es' : ''}
          </summary>
          <ul className="mt-1 space-y-0.5 pl-3 text-ink-secondary max-h-28 overflow-y-auto">
            {job.errors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </details>
      )}
    </div>
  )
}

// ── Tab: Colecciones ──────────────────────────────────────────────────────────

function CollectionsTab({ onOpen }: { onOpen: (name: string) => void }) {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['collections-list'],
    queryFn:  getCollectionList,
    staleTime: 30_000,
  })
  const [deleting, setDeleting] = useState<string | null>(null)

  async function handleDelete(name: string) {
    if (!window.confirm(`¿Eliminar permanentemente la colección "${name}"?\n\nEsta acción no se puede deshacer.`)) return
    setDeleting(name)
    try {
      await deleteCollection(name)
      queryClient.invalidateQueries({ queryKey: ['collections-list'] })
    } catch (err) {
      alert(`Error al eliminar: ${err instanceof Error ? err.message : err}`)
    } finally {
      setDeleting(null)
    }
  }

  if (isLoading) return (
    <div className="space-y-2 mt-4">
      {[1, 2, 3].map(i => <div key={i} className="h-12 rounded-card bg-surface-border/40 animate-pulse" />)}
    </div>
  )

  if (isError) return (
    <div className="mt-4 card p-6 text-center space-y-3">
      <p className="text-sm text-down">Error al cargar colecciones.</p>
      <button onClick={() => refetch()} className="btn-secondary text-xs">Reintentar</button>
    </div>
  )

  if (!data?.length) return (
    <div className="mt-4 card p-8 flex flex-col items-center gap-2 text-center">
      <Database className="w-8 h-8 text-ink-muted opacity-50" />
      <p className="text-sm text-ink-secondary">No hay colecciones en la base de datos.</p>
    </div>
  )

  return (
    <div className="mt-4 space-y-2">
      <div className="flex justify-end">
        <button onClick={() => refetch()} className="flex items-center gap-1 text-xs text-ink-muted hover:text-ink-primary transition-colors">
          <RefreshCw className="w-3 h-3" /> Actualizar
        </button>
      </div>
      {data.map((col: CollectionInfo) => (
        <div key={col.name} className="flex items-center justify-between px-3.5 py-3 rounded-card border border-surface-border bg-surface-raised gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className={`text-xs px-2 py-0.5 rounded-pill font-medium shrink-0 ${col.league === 'FBCYL' ? 'bg-accent-600/20 text-accent-400' : 'bg-brand-600/20 text-brand-400'}`}>
              {col.league}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-ink-primary truncate">{col.name}</p>
              <p className="text-xs text-ink-muted">
                {col.competition} · {col.season}{col.group ? ` · Grupo ${col.group}` : ''} · {col.game_count} partidos
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button onClick={() => onOpen(col.name)} className="p-1.5 rounded-lg hover:bg-surface-hover text-ink-muted hover:text-brand-400 transition-colors" title="Abrir">
              <ExternalLink className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => handleDelete(col.name)} disabled={deleting === col.name} className="p-1.5 rounded-lg hover:bg-surface-hover text-ink-muted hover:text-down transition-colors disabled:opacity-40" title="Eliminar">
              {deleting === col.name ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Shared: cascading select ──────────────────────────────────────────────────

function CascadeSelect({ label, options, value, onChange, loading, disabled, placeholder = 'Seleccionar…' }: {
  label: string; options: DropdownOption[]; value: string; onChange: (v: string) => void
  loading?: boolean; disabled?: boolean; placeholder?: string
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-ink-secondary flex items-center gap-1">
        {label}
        {loading && <Loader2 className="w-3 h-3 animate-spin text-ink-muted" />}
      </label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled || loading || options.length === 0}
        className="input text-sm disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <option value="">{options.length === 0 && !loading ? 'Sin opciones' : placeholder}</option>
        {options.map(o => <option key={o.value} value={o.value}>{o.text}</option>)}
      </select>
    </div>
  )
}

// ── Tab: Descargar FEB ────────────────────────────────────────────────────────

function FEBDownloadTab() {
  const queryClient = useQueryClient()
  const [compUrl, setCompUrl] = useState(''); const [compLabel, setCompLabel] = useState('')
  const [season,  setSeason]  = useState(''); const [seasonLabel, setSeasonLabel] = useState('')
  const [group,   setGroup]   = useState(''); const [groupLabel, setGroupLabel] = useState('')
  const [jobId,   setJobId]   = useState<string | null>(null)
  const [starting, setStarting] = useState(false); const [error, setError] = useState<string | null>(null)

  const { data: competitions, isLoading: loadingComps } = useQuery({
    queryKey: ['feb-competitions'], queryFn: getFebCompetitions, staleTime: 5 * 60_000,
  })
  const { data: seasons, isLoading: loadingSeasons } = useQuery({
    queryKey: ['feb-seasons', compUrl], queryFn: () => getFebSeasons(compUrl),
    enabled: !!compUrl, staleTime: 5 * 60_000,
  })
  const { data: groups, isLoading: loadingGroups } = useQuery({
    queryKey: ['feb-groups', compUrl, season], queryFn: () => getFebGroups(compUrl, season),
    enabled: !!compUrl && !!season, staleTime: 5 * 60_000,
  })

  function handleCompChange(url: string) {
    setCompUrl(url); setCompLabel(competitions?.find(c => c.results_url === url)?.name ?? '')
    setSeason(''); setSeasonLabel(''); setGroup(''); setGroupLabel(''); setJobId(null)
  }
  function handleSeasonChange(val: string) {
    setSeason(val); setSeasonLabel(seasons?.find(s => s.value === val)?.text ?? val)
    setGroup(''); setGroupLabel(''); setJobId(null)
  }
  function handleGroupChange(val: string) {
    setGroup(val); setGroupLabel(groups?.find(g => g.value === val)?.text ?? val); setJobId(null)
  }

  async function handleStart() {
    if (!compUrl || !season || !group) return
    setStarting(true); setError(null)
    try {
      const { job_id } = await postScrapeStart({
        league: 'FEB',
        feb: { competition_url: compUrl, season_value: season, group_value: group,
               competition_label: compLabel, season_label: seasonLabel, group_label: groupLabel },
      })
      setJobId(job_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar')
    } finally {
      setStarting(false)
    }
  }

  return (
    <div className="mt-4 space-y-4">
      <CascadeSelect label="Competición" options={(competitions ?? []).map(c => ({ text: c.name, value: c.results_url }))}
        value={compUrl} onChange={handleCompChange} loading={loadingComps} placeholder="Seleccionar competición…" />
      <CascadeSelect label="Temporada" options={seasons ?? []} value={season} onChange={handleSeasonChange}
        loading={loadingSeasons} disabled={!compUrl} placeholder="Seleccionar temporada…" />
      <CascadeSelect label="Grupo" options={groups ?? []} value={group} onChange={handleGroupChange}
        loading={loadingGroups} disabled={!season} placeholder="Seleccionar grupo…" />
      {error && (
        <div className="flex items-start gap-2 p-3 rounded-lg bg-down/10 border border-down/20 text-down text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />{error}
        </div>
      )}
      {!jobId && (
        <button onClick={handleStart} disabled={!compUrl || !season || !group || starting}
          className="btn-primary w-full justify-center gap-2 py-2.5 disabled:opacity-50">
          {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Iniciar descarga
        </button>
      )}
      {jobId && <ProgressPanel jobId={jobId} onDone={() => queryClient.invalidateQueries({ queryKey: ['collections-list'] })} />}
    </div>
  )
}

// ── Tab: Descargar FBCYL ──────────────────────────────────────────────────────

function FBCYLDownloadTab() {
  const queryClient = useQueryClient()
  const [season, setSeason] = useState(''); const [gender, setGender] = useState('')
  const [territory, setTerritory] = useState('0'); const [category, setCategory] = useState('')
  const [compId, setCompId] = useState(''); const [compLabel, setCompLabel] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [starting, setStarting] = useState(false); const [error, setError] = useState<string | null>(null)

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

  function handleSeasonChange(v: string)    { setSeason(v);    setCategory(''); setCompId(''); setJobId(null) }
  function handleGenderChange(v: string)    { setGender(v);    setCategory(''); setCompId(''); setJobId(null) }
  function handleTerritoryChange(v: string) { setTerritory(v); setCategory(''); setCompId(''); setJobId(null) }
  function handleCategoryChange(v: string)  { setCategory(v);  setCompId('');  setJobId(null) }
  function handleCompChange(v: string) {
    setCompId(v); setCompLabel(competitions?.find(c => c.value === v)?.text ?? v); setJobId(null)
  }

  async function handleStart() {
    if (!compId || !season || !category) return
    setStarting(true); setError(null)
    try {
      const { job_id } = await postScrapeStart({
        league: 'FBCYL',
        fbcyl: { competition_id: compId, competition_label: compLabel, season, gender, territory, category },
      })
      setJobId(job_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar')
    } finally {
      setStarting(false)
    }
  }

  return (
    <div className="mt-4 space-y-4">
      <CascadeSelect label="Temporada"   options={init?.seasons     ?? []} value={season}    onChange={handleSeasonChange}    loading={loadingInit}  placeholder="Seleccionar temporada…" />
      <CascadeSelect label="Género"      options={init?.genders     ?? []} value={gender}    onChange={handleGenderChange}    disabled={!season}     placeholder="Seleccionar género…" />
      <CascadeSelect label="Territorio"  options={init?.territories ?? []} value={territory} onChange={handleTerritoryChange} disabled={!season}     placeholder="Seleccionar territorio…" />
      <CascadeSelect label="Categoría"   options={categories ?? []}        value={category}  onChange={handleCategoryChange}  loading={loadingCats}  disabled={!season}    placeholder="Seleccionar categoría…" />
      <CascadeSelect label="Competición" options={competitions ?? []}       value={compId}    onChange={handleCompChange}      loading={loadingComps} disabled={!category}  placeholder="Seleccionar competición…" />
      {error && (
        <div className="flex items-start gap-2 p-3 rounded-lg bg-down/10 border border-down/20 text-down text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />{error}
        </div>
      )}
      {!jobId && (
        <button onClick={handleStart} disabled={!compId || !season || starting}
          className="btn-primary w-full justify-center gap-2 py-2.5 disabled:opacity-50">
          {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Iniciar descarga
        </button>
      )}
      {jobId && <ProgressPanel jobId={jobId} onDone={() => queryClient.invalidateQueries({ queryKey: ['collections-list'] })} />}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<Tab>('collections')

  return (
    <PageTransition>
      <div className="space-y-6 max-w-3xl mx-auto">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Administración</h1>
          <p className="text-ink-secondary text-sm mt-1">Gestión de colecciones y descarga de datos</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-surface-border">
          {TABS.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === tab.id
                  ? 'border-brand-500 text-brand-400'
                  : 'border-transparent text-ink-muted hover:text-ink-primary'
              }`}>
              {tab.label}
            </button>
          ))}
        </div>

        <div>
          {activeTab === 'collections' && <CollectionsTab onOpen={name => navigate(`/${encodeURIComponent(name)}`)} />}
          {activeTab === 'feb'         && <FEBDownloadTab />}
          {activeTab === 'fbcyl'       && <FBCYLDownloadTab />}
        </div>

        <div className="pt-4 border-t border-surface-border text-xs text-ink-muted space-y-1">
          <p><span className="font-medium">FEB:</span> Descarga partidos de las ligas nacionales FEB (L.F.2, EBA, etc.).</p>
          <p><span className="font-medium">FBCYL:</span> Descarga partidos de las ligas de Castilla y León.</p>
          <p className="flex items-center gap-1">
            <ChevronRight className="w-3 h-3" />
            Los datos nuevos incluyen metadatos de competición para análisis cruzado futuro.
          </p>
        </div>
      </div>
    </PageTransition>
  )
}

