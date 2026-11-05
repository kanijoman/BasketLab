/** Progress of a long task (issue #215): a bar and what it is doing with the step of the total. Used by the weekly report ZIP and the individual scouting DOCX. */
interface Props {
  step: number
  total: number
  message: string
}

export default function ProgressBar({ step, total, message }: Props) {
  const label = total > 0 ? `${message} (${step}/${total})` : message
  const share = total > 0 ? Math.min(step / total, 1) * 100 : 0
  return (
    <div className="flex flex-col gap-1">
      <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={total} aria-valuenow={step} className="h-1.5 w-full overflow-hidden rounded-full bg-surface-raised">
        <div className="h-full bg-secondary transition-all duration-500" style={{ width: `${share}%` }} />
      </div>
      <p className="text-center text-[11px] text-ink-muted">{label}</p>
    </div>
  )
}
