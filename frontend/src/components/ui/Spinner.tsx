/** Something is loading (issue #190): the spinner of the web, with its name for the screen reader. */
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

const SIZES = { sm: 'h-3.5 w-3.5', md: 'h-5 w-5', lg: 'h-8 w-8' } as const

export default function Spinner({ size = 'md', label = 'Cargando', className }: { size?: keyof typeof SIZES; label?: string; className?: string }) {
  return (
    <span role="status" aria-label={label} className={cn('inline-flex text-accent-text', className)}>
      <Loader2 className={cn('animate-spin', SIZES[size])} aria-hidden="true" />
    </span>
  )
}
