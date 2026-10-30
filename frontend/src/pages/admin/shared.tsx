/** What the tabs of Administración share (issue #195): the cascading select, the error of a start and the view of a job that runs. */
import type { ReactNode } from 'react'
import { AlertCircle, CheckCircle2 } from 'lucide-react'
import type { DropdownOption } from '@/api/client'
import { Field, Select } from '@/components/ui/Field'
import Spinner from '@/components/ui/Spinner'

export function CascadeSelect({ label, options, value, onChange, loading, disabled, placeholder = 'Seleccionar…' }: {
  label: string; options: DropdownOption[]; value: string; onChange: (v: string) => void
  loading?: boolean; disabled?: boolean; placeholder?: string
}) {
  return (
    <Field label={<span className="flex items-center gap-1">{label}{loading && <Spinner size="sm" label={`Cargando ${label.toLowerCase()}`} />}</span>}>
      <Select value={value} onChange={e => onChange(e.target.value)} disabled={disabled || loading || options.length === 0}>
        <option value="">{options.length === 0 && !loading ? 'Sin opciones' : placeholder}</option>
        {options.map(o => <option key={o.value} value={o.value}>{o.text}</option>)}
      </Select>
    </Field>
  )
}

export function StartError({ message }: { message: string }) {
  return (
    <div role="alert" className="flex items-start gap-2 p-3 rounded-lg bg-bad/10 border border-bad/20 text-bad text-sm">
      <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />{message}
    </div>
  )
}

export interface JobView {
  status: string
  done: number
  total: number
  currentMatch?: string | null
  errors: string[]
  /** What the job is called when it is done / fails / runs */
  texts: { done: string; error: string; running: string }
  aside?: string | null
  detail?: ReactNode
}

/** A job of the scraper or of the ingest: its state, its bar, the match it is on and its errors. */
export function JobStatus({ job }: { job: JobView }) {
  const pct = job.total > 0 ? Math.round((job.done / job.total) * 100) : 0
  const isDone = job.status === 'done'
  const isError = job.status === 'error'
  return (
    <div className="space-y-3 p-4 rounded-card border border-line bg-surface">
      <div className="flex items-center gap-2 text-sm">
        {isDone && <CheckCircle2 className="w-4 h-4 text-ok shrink-0" aria-hidden="true" />}
        {isError && <AlertCircle className="w-4 h-4 text-bad shrink-0" aria-hidden="true" />}
        {!isDone && !isError && <Spinner size="sm" label="En curso" className="text-accent-text shrink-0" />}
        <span className={isDone ? 'text-ok' : isError ? 'text-bad' : 'text-ink'}>
          {isDone ? job.texts.done : isError ? job.texts.error : job.texts.running}
        </span>
        {job.aside && <span className="ml-auto text-xs text-ink-faint font-mono truncate max-w-[14rem]">{job.aside}</span>}
      </div>
      {job.detail && !isDone && job.detail}
      {!isError && (
        <div role="progressbar" aria-label="Progreso" aria-valuemin={0} aria-valuemax={100} aria-valuenow={isDone ? 100 : pct} className="h-2 rounded-full bg-line overflow-hidden">
          <div className={`h-full rounded-full transition-all duration-500 ${isDone ? 'bg-ok' : 'bg-accent-solid'}`} style={{ width: isDone ? '100%' : `${pct}%` }} />
        </div>
      )}
      {job.currentMatch && !isDone && <p className="text-xs text-ink-faint font-mono truncate">Partido: {job.currentMatch}</p>}
      {job.errors.length > 0 && (
        <details className="text-xs">
          <summary className="text-bad cursor-pointer">{job.errors.length} error{job.errors.length > 1 ? 'es' : ''}</summary>
          <ul className="mt-1 space-y-0.5 pl-3 text-ink-muted max-h-28 overflow-y-auto">
            {job.errors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </details>
      )}
    </div>
  )
}
