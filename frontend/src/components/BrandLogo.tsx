/** The brand of the web (issues #189, #613): the mark of design/brand (the ball of the suite with the trend of the analysis, without the tile,
 *  as the live app shows its own) and the name. */
import mark from '@design/brand/web-mark.svg'
import { cn } from '@/lib/utils'

const SIZES = {
  sm: { mark: 'h-8 w-8', name: 'text-base', gap: 'gap-2' },
  lg: { mark: 'h-14 w-14', name: 'text-4xl', gap: 'gap-3' },
} as const

/** `product` is the third word of the family ("Talent", #877): BasketLab Analytics is just "BasketLab", as the live app is. */
export default function BrandLogo({ size = 'sm', nameClassName, product }: { size?: keyof typeof SIZES; nameClassName?: string; product?: string }) {
  const s = SIZES[size]
  return (
    <span className={cn('inline-flex items-center', s.gap)}>
      <img src={mark} alt="" className={cn('shrink-0', s.mark)} />
      <span className={cn('font-display font-bold tracking-tight text-ink', s.name, nameClassName)}>
        <span>Basket</span><span className="text-accent-text">Lab</span>
        {product && <span className="ml-1.5 font-medium text-ink-muted">{product}</span>}
      </span>
    </span>
  )
}
