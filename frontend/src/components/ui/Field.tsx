/**
 * Form controls of the web (issue #190): Input and Select (native, with a chevron) over the .input / .select classes of index.css,
 * and Field, which names its control and says its hint and its error (label, aria-describedby, aria-invalid). Guide: docs/UI.md.
 */
import { Children, cloneElement, forwardRef, isValidElement, useId, type InputHTMLAttributes, type ReactElement, type ReactNode, type SelectHTMLAttributes } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={cn('input', rest['aria-invalid'] && 'border-bad', className)} {...rest} />
})

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  /** The options, when they are a plain list (or give them as children) */
  options?: { value: string; label: string }[]
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select({ options, className, children, ...rest }, ref) {
  return (
    <span className="relative inline-flex w-full">
      <select ref={ref} className={cn('select pr-8', rest['aria-invalid'] && 'border-bad', className)} {...rest}>
        {options ? options.map(o => <option key={o.value} value={o.value}>{o.label}</option>) : children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
    </span>
  )
})

interface FieldProps {
  label: ReactNode
  hint?: ReactNode
  error?: ReactNode
  className?: string
  /** One control: Input, Select or any element that takes id and aria-* */
  children: ReactElement
}

export function Field({ label, hint, error, className, children }: FieldProps) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const control = Children.only(children)
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <label htmlFor={id} className="text-xs font-medium text-ink-muted">{label}</label>
      {isValidElement(control) && cloneElement(control as ReactElement<Record<string, unknown>>, {
        id,
        'aria-describedby': [hintId, errorId].filter(Boolean).join(' ') || undefined,
        'aria-invalid': error ? true : undefined,
      })}
      {hint && <p id={hintId} className="text-xs text-ink-faint">{hint}</p>}
      {error && <p id={errorId} className="text-xs text-bad">{error}</p>}
    </div>
  )
}
