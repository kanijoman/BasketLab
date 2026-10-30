/** Tab "Histórico": what HISTORICAL holds and the ingest of past FEB seasons into it (issue #195: seasons as Checkbox, buttons as Button). */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Play, RefreshCw } from 'lucide-react'
import { getFebCompetitions, getFebSeasons, getHistoricalSummary, postCompetitionIngest, type HistoricalSummaryEntry } from '@/api/client'
import Button from '@/components/ui/Button'
import Checkbox from '@/components/ui/Checkbox'
import { HistoricalProgressPanel } from './ProgressPanels'
import { CascadeSelect, StartError } from './shared'

function SummaryTable({ summary }: { summary: HistoricalSummaryEntry[] }) {
  return (
    <div className="rounded-card border border-line overflow-hidden">
      <table className="w-full text-xs">
        <thead className="bg-surface">
          <tr>{['Liga', 'Competición', 'Temporada', 'Grupo', 'Partidos'].map(h => (
            <th key={h} className="px-3 py-2 text-left font-medium text-ink-muted">{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {summary.map((row, i) => (
            <tr key={i} className="border-t border-line hover:bg-surface-raised/50">
              <td className="px-3 py-2">{row.league}</td>
              <td className="px-3 py-2">{row.competition}</td>
              <td className="px-3 py-2">{row.season}</td>
              <td className="px-3 py-2">{row.group || '—'}</td>
              <td className="px-3 py-2 font-medium">{Math.round(row.match_count)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function HistoricalTab() {
  const { data: summary, isLoading: loadingSummary, refetch } = useQuery({
    queryKey: ['historical-summary'],
    queryFn: getHistoricalSummary,
    staleTime: 30_000,
  })

  const [compUrl, setCompUrl]     = useState('')
  const [compLabel, setCompLabel] = useState('')
  const [checked, setChecked]     = useState<Set<string>>(new Set())
  const [jobId, setJobId]         = useState<string | null>(null)
  const [starting, setStarting]   = useState(false)
  const [error, setError]         = useState<string | null>(null)

  const { data: competitions, isLoading: loadingComps } = useQuery({
    queryKey: ['feb-competitions'], queryFn: getFebCompetitions, staleTime: 5 * 60_000,
  })
  const { data: seasons, isLoading: loadingSeasons } = useQuery({
    queryKey: ['feb-seasons', compUrl],
    queryFn: () => getFebSeasons(compUrl),
    enabled: !!compUrl,
    staleTime: 5 * 60_000,
  })

  function handleCompChange(url: string) {
    setCompUrl(url)
    setCompLabel(competitions?.find(c => c.results_url === url)?.name ?? '')
    setChecked(new Set())
  }

  function toggleSeason(value: string) {
    setChecked(prev => {
      const next = new Set(prev)
      if (next.has(value)) next.delete(value)
      else next.add(value)
      return next
    })
  }

  async function handleStart() {
    if (checked.size === 0 || !compUrl) return
    setStarting(true); setError(null)
    try {
      const seasonsToIngest = (seasons ?? [])
        .filter(s => checked.has(s.value))
        .map(s => ({ season_value: s.value, season_label: s.text }))
      const { job_id } = await postCompetitionIngest({ competition_url: compUrl, competition_label: compLabel, seasons: seasonsToIngest })
      setJobId(job_id)
      setChecked(new Set())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar')
    } finally {
      setStarting(false)
    }
  }

  const allValues = seasons?.map(s => s.value) ?? []

  return (
    <div className="mt-4 space-y-6">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">Contenido actual de HISTORICAL</h2>
          <Button variant="ghost" size="sm" icon={RefreshCw} onClick={() => refetch()}>Actualizar</Button>
        </div>
        {loadingSummary && <div className="h-8 rounded-card bg-line/40 animate-pulse" aria-hidden="true" />}
        {!loadingSummary && (!summary || summary.length === 0) && <p className="text-sm text-ink-muted">Sin datos históricos todavía.</p>}
        {summary && summary.length > 0 && <SummaryTable summary={summary} />}
      </div>

      <div className="space-y-4">
        <h2 className="text-sm font-semibold text-ink">Descargar temporadas FEB → HISTORICAL</h2>

        <CascadeSelect label="Competición" options={(competitions ?? []).map(c => ({ text: c.name, value: c.results_url }))}
          value={compUrl} onChange={handleCompChange} loading={loadingComps} placeholder="Seleccionar competición…" />

        {compUrl && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-ink-muted">Temporadas disponibles</span>
              {allValues.length > 0 && (
                <div className="flex gap-1">
                  <Button variant="ghost" size="sm" onClick={() => setChecked(new Set(allValues))}>Todas</Button>
                  <Button variant="ghost" size="sm" onClick={() => setChecked(new Set())}>Ninguna</Button>
                </div>
              )}
            </div>

            {loadingSeasons && (
              <div className="space-y-1" aria-hidden="true">
                {[1, 2, 3].map(i => <div key={i} className="h-9 rounded bg-line/40 animate-pulse" />)}
              </div>
            )}

            {!loadingSeasons && seasons && seasons.length > 0 && (
              <div className="rounded-card border border-line divide-y divide-line max-h-56 overflow-y-auto">
                {seasons.map(s => (
                  <Checkbox key={s.value} label={s.text} checked={checked.has(s.value)} onChange={() => toggleSeason(s.value)}
                    className="gap-3 px-3 py-2.5 text-sm text-ink hover:bg-surface-raised/60 transition-colors select-none" />
                ))}
              </div>
            )}

            {!loadingSeasons && seasons && seasons.length === 0 && (
              <p className="text-sm text-ink-muted">No se encontraron temporadas para esta competición.</p>
            )}
          </div>
        )}

        {error && <StartError message={error} />}

        {!jobId && (
          <Button icon={Play} loading={starting} disabled={checked.size === 0} onClick={handleStart} className="w-full justify-center py-2.5">
            Descargar {checked.size > 0 ? checked.size : ''} temporada{checked.size !== 1 ? 's' : ''}
            {checked.size > 0 ? ' (todos los grupos)' : ''}
          </Button>
        )}

        {jobId && <HistoricalProgressPanel jobId={jobId} />}
      </div>
    </div>
  )
}
