/** The shape of what is loading (issue #190): one block, or `lines` bars of text. Hidden from the screen reader (a Spinner says it). */
import { cn } from '@/lib/utils'

export default function Skeleton({ lines, className }: { lines?: number; className?: string }) {
  if (!lines) return <div aria-hidden="true" className={cn('animate-pulse rounded bg-line/50', className ?? 'h-4 w-full')} />
  return (
    <div aria-hidden="true" className={cn('animate-pulse space-y-2', className)}>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className={cn('h-3.5 rounded bg-line/50', i === lines - 1 && lines > 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  )
}
