/**
 * Tooltip — portal-based hover tooltip.
 *
 * Renders the bubble into `document.body` via `createPortal` so it is never
 * clipped by `overflow-hidden` / `overflow-x-auto` parent containers
 * (e.g. the DataTable scroll wrapper).
 *
 * Also exports `tippedHeader(abbr)` — TanStack Table-compatible header factory.
 */
import { useState } from 'react'
import { createPortal } from 'react-dom'
import type { ReactNode } from 'react'
import { STAT_LABELS } from '@/lib/statLabels'

// -- Component -----------------------------------------------------------------

interface TooltipProps {
  /** Tooltip content shown on hover */
  text: string
  children: ReactNode
  className?: string
}

interface Pos { x: number; y: number; w: number }

/**
 * Wraps `children` in a span that shows a fixed-position tooltip on hover.
 * The bubble is rendered via React portal directly into `document.body`,
 * bypassing any overflow constraints from ancestor elements.
 */
export default function Tooltip({ text, children, className }: TooltipProps) {
  const [pos, setPos] = useState<Pos | null>(null)

  function handleEnter(e: React.MouseEvent) {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
    setPos({ x: r.left + r.width / 2, y: r.top, w: r.width })
  }

  return (
    <span
      className={`cursor-help inline-flex items-center ${className ?? ''}`}
      onMouseEnter={handleEnter}
      onMouseLeave={() => setPos(null)}
    >
      {children}

      {pos && createPortal(
        <span
          role="tooltip"
          style={{
            position: 'fixed',
            top:  pos.y - 8,
            left: pos.x,
            transform: 'translate(-50%, -100%)',
            zIndex: 9999,
          }}
          className={[
            'pointer-events-none w-max max-w-[240px] rounded-md px-2.5 py-1.5',
            'bg-gray-900 text-gray-100 text-[11px] leading-snug font-normal',
            'shadow-xl whitespace-normal text-center border border-gray-700',
          ].join(' ')}
        >
          {text}
          {/* Downward caret */}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </span>,
        document.body,
      )}
    </span>
  )
}

// -- tippedHeader factory -------------------------------------------------------

/**
 * Returns a TanStack Table `header` value for a column abbreviation.
 *
 * - If `abbr` is in STAT_LABELS → returns a render function that wraps the
 *   abbreviation in a `<Tooltip>` showing the label + description.
 * - Otherwise → returns `abbr` unchanged (zero-regression path).
 *
 * Usage in a ColDef:
 * ```ts
 * { id: 'oer', accessorKey: 'oer', header: tippedHeader('OER') }
 * ```
 */
export function tippedHeader(abbr: string): string | (() => JSX.Element) {
  const entry = STAT_LABELS[abbr]
  if (!entry) return abbr

  const tipText = `${entry.label}: ${entry.description}`
  // Return a zero-arg render function — compatible with TanStack Table's
  // ColumnDefTemplate which accepts `string | ((props: HeaderContext) => ReactNode)`.
  // TypeScript allows fewer-parameter functions to fill a wider callback type.
  return () => (
    <Tooltip text={tipText}>
      <span className="underline decoration-dotted underline-offset-2">{abbr}</span>
    </Tooltip>
  )
}
