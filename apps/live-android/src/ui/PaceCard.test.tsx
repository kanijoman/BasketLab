import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PaceCard from './PaceCard'
import type { PaceAnalysis } from '../engine/types'

const OWN = { id: '1', name: 'MIPELLETYMAS B.F. LEON' }
const RIVAL = { id: '2', name: 'RECOLETAS ZAMORA' }

const PACE: PaceAnalysis = {
  reliable: true, possessions: 36, current40: 72, habit_own40: 70, habit_rival40: 62,
  delta_own: 2, delta_rival: 10, projected_possessions: 72.4,
  sample_games: { own: 4, rival: 3 },
}

const row = (name: RegExp) => screen.getByText(name).closest('li') as HTMLElement

describe('PaceCard', () => {
  it('shows the current pace, the projection and the +/- against both habitual paces', () => {
    render(<PaceCard pace={PACE} own={OWN} rival={RIVAL} />)
    expect(screen.getByText('72,0')).toBeTruthy()
    expect(screen.getByText(/Proyección final: ≈ 72 posesiones por equipo/i)).toBeTruthy()
    expect(within(row(/MIPELLETYMAS/)).getByText('+2,0')).toBeTruthy()
    expect(within(row(/RECOLETAS/)).getByText('+10,0')).toBeTruthy()
  })

  it('says how many games the habitual pace comes from', () => {
    render(<PaceCard pace={PACE} own={OWN} rival={RIVAL} />)
    expect(within(row(/MIPELLETYMAS/)).getByText(/70,0.*4 partidos/)).toBeTruthy()
    expect(within(row(/RECOLETAS/)).getByText(/62,0.*3 partidos/)).toBeTruthy()
  })

  it('uses the singular when the habitual pace comes from a single game', () => {
    render(<PaceCard pace={{ ...PACE, sample_games: { own: 1, rival: 3 } }} own={OWN} rival={RIVAL} />)
    expect(within(row(/MIPELLETYMAS/)).getByText(/1 partido(?!s)/)).toBeTruthy()
  })

  it('a slower game than usual is shown with a minus sign and in words', () => {
    render(<PaceCard pace={{ ...PACE, delta_own: -4.5 }} own={OWN} rival={RIVAL} />)
    const own = row(/MIPELLETYMAS/)
    expect(within(own).getByText('-4,5')).toBeTruthy()
    expect(within(own).getByText(/más lento/i)).toBeTruthy()
    expect(within(row(/RECOLETAS/)).getByText(/más rápido/i)).toBeTruthy()
  })

  it('a difference under one possession is "como siempre"', () => {
    render(<PaceCard pace={{ ...PACE, delta_own: 0.4 }} own={OWN} rival={RIVAL} />)
    expect(within(row(/MIPELLETYMAS/)).getByText(/como siempre/i)).toBeTruthy()
  })

  it('without a habitual pace in the package (old packages) the row shows a dash, not a wrong number', () => {
    render(<PaceCard pace={{ ...PACE, habit_rival40: null, delta_rival: null }} own={OWN} rival={RIVAL} />)
    const rival = row(/RECOLETAS/)
    expect(within(rival).getByText('—')).toBeTruthy()
    expect(within(rival).getByText(/sin dato/i)).toBeTruthy()
  })

  it('waits while the first minutes are too noisy', () => {
    render(<PaceCard pace={{ ...PACE, reliable: false }} own={OWN} rival={RIVAL} />)
    expect(screen.getByText(/calculando/i)).toBeTruthy()
    expect(screen.getByText(/5 minutos/i)).toBeTruthy()
    expect(screen.queryByText('72,0')).toBeNull()
  })

  it('waits when the engine has not produced any analysis yet', () => {
    render(<PaceCard pace={null} own={OWN} rival={RIVAL} />)
    expect(screen.getByText(/calculando/i)).toBeTruthy()
  })
})
