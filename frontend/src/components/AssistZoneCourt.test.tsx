import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import AssistZoneCourt from './AssistZoneCourt'

// Issue #773: one court, one bubble per zone: its size is how many baskets the player scored there, the coloured part of the ring is the share that was assisted.
const ZONES = [
  { zone: 'key_area', assisted: 3, unassisted: 1, assisted_pct: 75 },
  { zone: 'center_three', assisted: 0, unassisted: 2, assisted_pct: 0 },
  { zone: 'left_corner_three', assisted: 2, unassisted: 0, assisted_pct: 100 },
]

describe('AssistZoneCourt', () => {
  it('draws one bubble per zone with the baskets and the share assisted, and only for the zones with baskets', () => {
    const { container } = render(<AssistZoneCourt zones={[...ZONES, { zone: 'left_wing_three', assisted: 0, unassisted: 0, assisted_pct: null }]} />)
    expect(container.querySelectorAll('[data-zone]')).toHaveLength(3)
    const paint = container.querySelector('[data-zone="key_area"]')!
    expect(paint.textContent).toContain('4')
    expect(paint.textContent).toContain('75%')
    expect(container.querySelector('[data-zone="center_three"]')!.textContent).toContain('0%')
  })

  it('says in a legend what the two colours are and what the size is, so nothing has to be guessed', () => {
    render(<AssistZoneCourt zones={ZONES} />)
    expect(screen.getByText('Con asistencia')).toBeInTheDocument()
    expect(screen.getByText('Sin asistencia')).toBeInTheDocument()
    expect(screen.getByText(/tamaño.*canastas/i)).toBeInTheDocument()
  })

  it('a bubble fully assisted or fully unassisted is a single colour (no empty slice)', () => {
    const { container } = render(<AssistZoneCourt zones={ZONES} />)
    expect(container.querySelector('[data-zone="left_corner_three"] path')).toBeNull()
    expect(container.querySelector('[data-zone="center_three"] path')).toBeNull()
    expect(container.querySelector('[data-zone="key_area"] path')).not.toBeNull()
  })

  it('without any zone it says there is nothing to draw instead of an empty court', () => {
    render(<AssistZoneCourt zones={[]} />)
    expect(screen.getByText(/sin canastas con zona/i)).toBeInTheDocument()
  })

  it('says how many baskets have no known zone, so the court is not read as the whole story', () => {
    render(<AssistZoneCourt zones={ZONES} withoutZone={3} />)
    expect(screen.getByText(/3 canastas sin zona/i)).toBeInTheDocument()
  })
})
