/**
 * A checkbox with its label (issue #193): the native control, named by the text beside it and clickable by it. For an option that is on or off
 * (the series of a chart, a filter); a choice among a few is a SegmentedControl. Guide: docs/UI.md.
 */
import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: ReactNode
  /** The classes of the whole label (its layout in the row) */
  className?: string
}

const Checkbox = forwardRef<HTMLInputElement, Props>(function Checkbox({ label, className, ...rest }, ref) {
  return (
    <label className={cn('flex cursor-pointer items-center gap-1.5 text-xs text-ink-muted', rest.disabled && 'cursor-not-allowed opacity-60', className)}>
      <input ref={ref} type="checkbox" className="rounded accent-accent" {...rest} />
      <span>{label}</span>
    </label>
  )
})
export default Checkbox
