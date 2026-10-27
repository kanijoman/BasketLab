/** The brand of the web (issue #189): the icon of design/brand (the ball of the suite with the bars of analysis) and the name. */
import icon from '@design/brand/web-icon.svg'
import { cn } from '@/lib/utils'

const SIZES = {
  sm: { mark: 'h-8 w-8', name: 'text-base', gap: 'gap-2' },
  lg: { mark: 'h-14 w-14', name: 'text-4xl', gap: 'gap-3' },
} as const

export default function BrandLogo({ size = 'sm', nameClassName }: { size?: keyof typeof SIZES; nameClassName?: string }) {
  const s = SIZES[size]
  return (
    <span className={cn('inline-flex items-center', s.gap)}>
      <img src={icon} alt="" className={cn('shrink-0', s.mark)} />
      <span className={cn('font-display font-bold tracking-tight text-ink', s.name, nameClassName)}>
        <span>Basket</span><span className="text-accent-text">Lab</span>
      </span>
    </span>
  )
}
