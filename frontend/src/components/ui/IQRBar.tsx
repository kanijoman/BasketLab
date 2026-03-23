/**
 * IQRBar — mini horizontal bar showing a value's position within a distribution.
 *
 * Renders a slim (4px) bar with:
 *  - Full range (min → max) as grey background
 *  - Interquartile range (Q1 → Q3) as a highlighted band
 *  - Current value as a white tick mark
 *
 * Designed to be embedded below the numeric value in DataTable cells for
 * "always-visible" dispersion context.
 */

interface IQRBarProps {
  value: number
  min: number
  q1: number
  q3: number
  max: number
  /** Lower value = better (e.g. DER, turnovers) */
  reverse?: boolean
  className?: string
}

export default function IQRBar({ value, min, q1, q3, max, reverse = false, className }: IQRBarProps) {
  const range = max - min
  if (range <= 0) return null

  // Clamp value within [min, max] for display purposes
  const clamped = Math.min(Math.max(value, min), max)

  // Convert absolute values to percentages within [min, max]
  const pct = (v: number) => ((v - min) / range) * 100

  const iqrLeft   = pct(q1)
  const iqrWidth  = pct(q3) - pct(q1)
  const valuePct  = pct(clamped)

  // IQR band colour: green when direction is favourable, amber when not
  // A value in Q3-Q4 is best for non-reversed stats (high = good)
  // A value in Q1-Q2 is best for reversed stats (low = good)
  const iqrColor = reverse ? 'bg-slate-500/40' : 'bg-brand-500/40'

  return (
    <span
      className={`relative block w-full h-[4px] rounded-full bg-surface-border overflow-visible ${className ?? ''}`}
      title={`Rango: ${min.toFixed(1)} – ${max.toFixed(1)}  |  IQR: ${q1.toFixed(1)} – ${q3.toFixed(1)}`}
    >
      {/* IQR band */}
      <span
        className={`absolute inset-y-0 rounded-full ${iqrColor}`}
        style={{ left: `${iqrLeft}%`, width: `${iqrWidth}%` }}
      />
      {/* Value tick */}
      <span
        className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-[3px] h-[8px] rounded-full bg-white shadow-sm"
        style={{ left: `${valuePct}%` }}
      />
    </span>
  )
}
