/** The progress of the two jobs of Administración: the download of a competition (scraper) and the ingest of past seasons (HISTORICAL). */
import { useEffect, useState } from 'react'
import { getHistoricalProgress, getScrapeProgress, type HistoricalJob, type ScrapeJob } from '@/api/client'
import Spinner from '@/components/ui/Spinner'
import { JobStatus } from './shared'

const Starting = ({ text }: { text: string }) => (
  <div className="flex items-center gap-2 text-sm text-ink-muted p-4"><Spinner size="sm" label={text} /> {text}</div>
)

/** Asks for the job every `every` ms until it is done or fails (or the request fails). */
function useJob<T extends { status: string }>(jobId: string, load: (id: string) => Promise<T>, every: number, onDone?: () => void): T | null {
  const [job, setJob] = useState<T | null>(null)
  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const data = await load(jobId)
        setJob(data)
        if (data.status === 'done' || data.status === 'error') {
          clearInterval(timer)
          if (data.status === 'done') onDone?.()
        }
      } catch {
        clearInterval(timer)
      }
    }, every)
    return () => clearInterval(timer)
  }, [jobId, load, every, onDone])
  return job
}

export function ProgressPanel({ jobId, onDone }: { jobId: string; onDone: () => void }) {
  const job = useJob<ScrapeJob>(jobId, getScrapeProgress, 1000, onDone)
  if (!job) return <Starting text="Iniciando descarga…" />
  return (
    <JobStatus job={{
      status: job.status, done: job.done, total: job.total, currentMatch: job.current_match, errors: job.errors, aside: job.collection,
      texts: { done: `Descarga completada — ${job.done} partidos`, error: 'Error durante la descarga', running: `Descargando… ${job.done} / ${job.total ?? '?'}` },
    }} />
  )
}

export function HistoricalProgressPanel({ jobId }: { jobId: string }) {
  const job = useJob<HistoricalJob>(jobId, getHistoricalProgress, 1500)
  if (!job) return <Starting text="Iniciando…" />
  return (
    <JobStatus job={{
      status: job.status, done: job.done, total: job.total, currentMatch: job.current_match, errors: job.errors,
      texts: { done: `Ingesta completada — ${job.done} partidos procesados`, error: 'Error durante la ingesta', running: `Procesando… ${job.done} / ${job.total ?? '?'}` },
      detail: job.current_season && <p className="text-xs text-ink-faint">Temporada activa: <span className="font-medium">{job.current_season}</span></p>,
    }} />
  )
}
