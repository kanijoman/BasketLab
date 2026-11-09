import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PassZoneCourt from './PassZoneCourt'

// Issue #773, the passer's side: from where the players a passer finds score. One bubble per zone: its size is the number of assists that end there.
const ZONES = [
  { zone: 'paint', count: 6 },
  { zone: 'top_three', count: 3 },
  { zone: 'corner_left', count: 1 },
]

describe('PassZoneCourt', () => {
  it('draws one bubble per zone with the assists that end there and their share of all the assists of the passer', () => {
    const { container } = render(<PassZoneCourt zones={ZONES} />)
    expect(container.querySelectorAll('[data-pass-zone]')).toHaveLength(3)
    const paint = container.querySelector('[data-pass-zone="paint"]')!
    expect(paint.textContent).toContain('6')
    expect(paint.textContent).toContain('60%')                                   // 6 of the 10 assists
    expect(container.querySelector('[data-pass-zone="corner_left"]')!.textContent).toContain('10%')
  })

  it('the share counts the assists with no known zone too, so the percentages are not inflated', () => {
    const { container } = render(<PassZoneCourt zones={ZONES} withoutZone={10} />)
    expect(container.querySelector('[data-pass-zone="paint"]')!.textContent).toContain('30%')           // 6 of 20
  })

  it('draws no bubble for a zone without assists', () => {
    const { container } = render(<PassZoneCourt zones={[...ZONES, { zone: 'wing_left', count: 0 }]} />)
    expect(container.querySelectorAll('[data-pass-zone]')).toHaveLength(3)
  })

  it('says in its caption what the size and the small figure are, so nothing has to be guessed', () => {
    render(<PassZoneCourt zones={ZONES} />)
    expect(screen.getByText(/tamaño.*asistencias/i)).toBeInTheDocument()
  })

  it('says how many of his assists end in a basket with no known zone', () => {
    render(<PassZoneCourt zones={ZONES} withoutZone={2} />)
    expect(screen.getByText(/2 asistencias sin zona/i)).toBeInTheDocument()
  })

  it('without any zone it says there is nothing to draw instead of an empty court', () => {
    render(<PassZoneCourt zones={[]} />)
    expect(screen.getByText(/sin asistencias con zona/i)).toBeInTheDocument()
  })

  // Issue #803: the orange ring was always a full circle. It is an arc from the top, clockwise, of the share that is written inside (as in AssistZoneCourt).
  describe('the ring says the share (issue #803)', () => {
    /** Degrees of the circle that the arc of a bubble covers, read from its path `M cx cy-r A r r 0 large 1 x y` (null: no arc). */
    const sweep = (container: HTMLElement, zone: string): number | null => {
      const d = container.querySelector(`[data-pass-zone="${zone}"] path`)?.getAttribute('d')
      if (!d) return null
      const [cx, top, r, large, x, y] = d.match(/M (\S+) (\S+) A (\S+) \S+ 0 ([01]) 1 (\S+) (\S+)/)!.slice(1).map(Number)
      const degrees = (Math.atan2(x - cx, top + r - y) * 180) / Math.PI                // clockwise from the top, in (-180, 180]
      return large === 1 ? (degrees + 360) % 360 : degrees
    }

    it('covers the share of each zone: 60 % of the circle for 6 of 10, 10 % for 1 of 10', () => {
      const { container } = render(<PassZoneCourt zones={ZONES} />)
      expect(sweep(container, 'paint')).toBeCloseTo(0.6 * 360, 0)
      expect(sweep(container, 'top_three')).toBeCloseTo(0.3 * 360, 0)
      expect(sweep(container, 'corner_left')).toBeCloseTo(0.1 * 360, 0)
    })

    it('counts the assists with no known zone in the total, as the figure does', () => {
      const { container } = render(<PassZoneCourt zones={ZONES} withoutZone={10} />)
      expect(sweep(container, 'paint')).toBeCloseTo(0.3 * 360, 0)           // 6 of 20
    })

    it('a zone with all the assists is a full ring of one colour, with no arc', () => {
      const { container } = render(<PassZoneCourt zones={[{ zone: 'paint', count: 4 }]} />)
      expect(container.querySelector('[data-pass-zone="paint"] path')).toBeNull()
      expect(container.querySelectorAll('[data-pass-zone="paint"] circle')).toHaveLength(2)
    })
  })
})
