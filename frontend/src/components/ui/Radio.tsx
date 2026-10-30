/**
 * A radio with its label (issue #195): the native control, named by the text beside it and chosen by it. For a long option among a few in a form (a match
 * with its date and rival); a short choice inside a view is a SegmentedControl. Guide: docs/UI.md.
 */
import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: ReactNode
  /** The classes of the whole label (its layout in the row) */
  className?: string
}

const Radio = forwardRef<HTMLInputElement, Props>(function Radio({ label, className, ...rest }, ref) {
  return (
    <label className={cn('flex cursor-pointer items-center gap-2 text-sm text-ink-muted', rest.disabled && 'cursor-not-allowed opacity-60', className)}>
      <input ref={ref} type="radio" className="accent-accent" {...rest} />
      <span>{label}</span>
    </label>
  )
})
export default Radio
