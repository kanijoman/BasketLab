/**
 * Buttons of the web (issue #190). The styles are the .btn-* classes of index.css (one source, while the pages still use them raw);
 * `type="button"` by default, so a button inside a form never submits it by accident. Guide: docs/UI.md.
 */
import { forwardRef, type ButtonHTMLAttributes } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import Spinner from './Spinner'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  /** An icon before the text (replaced by the spinner while loading) */
  icon?: LucideIcon
  /** Busy: disabled, with a spinner, until the work ends */
  loading?: boolean
}

const SMALL = 'px-3 py-1.5 text-xs'

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', icon: Icon, loading = false, disabled, type = 'button', className, children, ...rest }, ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(`btn-${variant}`, size === 'sm' && SMALL, className)}
      {...rest}
    >
      {loading ? <Spinner size="sm" className="text-current" /> : Icon && <Icon className={size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} aria-hidden="true" />}
      {children}
    </button>
  )
})
export default Button

/** A button with an icon only: `label` is its name for the screen reader and its tooltip. */
export const IconButton = forwardRef<HTMLButtonElement, Omit<ButtonProps, 'icon' | 'children'> & { icon: LucideIcon; label: string }>(function IconButton(
  { icon: Icon, label, variant = 'ghost', size = 'md', className, ...rest }, ref,
) {
  return (
    <Button ref={ref} variant={variant} aria-label={label} title={label} className={cn(size === 'sm' ? 'p-1' : 'p-1.5', className)} {...rest}>
      <Icon className={size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} aria-hidden="true" />
    </Button>
  )
})
