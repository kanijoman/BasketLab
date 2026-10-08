import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FibaCourtSVG from './FibaCourtSVG'
import { RATING_COLOR } from '@/lib/zoneRating'
import type { ShotZoneData } from '@/api/client'

const zone = (key: string, over: Partial<ShotZoneData> = {}): ShotZoneData => ({
  zone: key, zone_label: key, points: 2, fga: 40, fgm: 20, fg_pct: 50, ...over,
})

function fills(zones: ShotZoneData[]): string[] {
  const { container } = render(<FibaCourtSVG zones={zones} vizMode="zones" />)
  return Array.from(container.querySelectorAll('circle'))
    .map(c => c.getAttribute('fill') ?? '')
    .filter(f => f.startsWith('#'))
}

describe('FibaCourtSVG zone colours', () => {
  it('colours zones by their rating against the league, not by a fixed FG%', () => {
    const colours = fills([
      zone('paint', { rating: 'above', fg_pct: 30 }),   // 30 % but above league → green
      zone('mid_left', { rating: 'below', fg_pct: 70 }), // 70 % but below league → red
      zone('mid_right', { rating: 'average' }),
    ])
    expect(colours).toContain(RATING_COLOR.above)
    expect(colours).toContain(RATING_COLOR.below)
    expect(colours).toContain(RATING_COLOR.average)
  })

  it('does not use a hue computed from the raw percentage', () => {
    const { container } = render(<FibaCourtSVG zones={[zone('paint', { rating: 'average', fg_pct: 38 })]} vizMode="zones" />)
    expect(container.innerHTML).not.toMatch(/hsl\(/)
  })

  it('shows a legend with the three ratings in zones mode', () => {
    const { container } = render(<FibaCourtSVG zones={[zone('paint', { rating: 'above' })]} vizMode="zones" />)
    const text = container.textContent ?? ''
    expect(text).toMatch(/encima/i)
    expect(text).toMatch(/promedio/i)
    expect(text).toMatch(/debajo/i)
  })

  it('flags zones with a small sample', () => {
    const { container } = render(<FibaCourtSVG zones={[zone('paint', { rating: 'above', low_sample: true, fga: 3 })]} vizMode="zones" />)
    expect(container.querySelector('[data-low-sample="true"]')).not.toBeNull()
  })
})
