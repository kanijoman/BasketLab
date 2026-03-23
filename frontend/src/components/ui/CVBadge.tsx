/**
 * CVBadge — intra-team game-to-game variability indicator.
 *
 * Shows as a tiny "σ XX%" chip next to a stat value, colour-coded by severity:
 *   CV < 15 %  → slate/dim   (consistent, predictable)
 *   CV 15-30 % → amber       (moderate variance)
 *   CV > 30 %  → red         (high variance, volatile)
 *
 * Hovering reveals std dev and mean alongside the interpretation.
 */
import Tooltip from '@/components/ui/Tooltip'

export interface CVEntry {
  mean: number
  std: number
  cv: number
  n: number
}

interface CVBadgeProps {
  entry: CVEntry
}

/** Returns Tailwind classes for the pill background + text so it remains
 *  readable on any quartile cell background (green Q1 through red Q4). */
function cvClass(cv: number): string {
  if (cv >= 30) return 'bg-red-950 text-red-300 ring-1 ring-red-800'
  if (cv >= 15) return 'bg-amber-950 text-amber-300 ring-1 ring-amber-800'
  return 'bg-zinc-800 text-zinc-400 ring-1 ring-zinc-600'
}

function cvLabel(cv: number): string {
  if (cv >= 30) return 'Alta variabilidad'
  if (cv >= 15) return 'Variabilidad moderada'
  return 'Consistente'
}

export default function CVBadge({ entry }: CVBadgeProps) {
  const { mean, std, cv, n } = entry
  const tipText =
    `${cvLabel(cv)} partido a partido\n` +
    `Media: ${mean.toFixed(1)}  ·  σ: ${std.toFixed(1)}  ·  CV: ${cv.toFixed(1)}%\n` +
    `(sobre ${n} partidos)`

  return (
    <Tooltip text={tipText}>
      <span className={`inline-block px-1 rounded text-[10px] font-mono leading-none ${cvClass(cv)}`}>
        σ{cv.toFixed(0)}%
      </span>
    </Tooltip>
  )
}
