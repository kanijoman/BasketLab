import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Scoreboard from './Scoreboard'

const OWN = { id: '1008631', name: 'MIPELLETYMAS B.F. LEON' }
const RIVAL = { id: '1008898', name: 'RECOLETAS ZAMORA' }

const sides = () => Array.from(document.querySelectorAll('.scoreboard .team')) as HTMLElement[]

describe('Scoreboard', () => {
  it('shows the local team on the left and the visitor on the right, with their scores', () => {
    render(<Scoreboard own={OWN} rival={RIVAL} homeId="1008898" score={{ '1008631': 38, '1008898': 59 }} clock="Q4 00:00" />)
    const [left, right] = sides()
    expect(within(left).getByText('RECOLETAS ZAMORA')).toBeTruthy()
    expect(within(left).getByText('59')).toBeTruthy()
    expect(within(right).getByText('MIPELLETYMAS B.F. LEON')).toBeTruthy()
    expect(within(right).getByText('38')).toBeTruthy()
    expect(screen.getByText('Q4 00:00')).toBeTruthy()
  })

  it('marks which one is our team', () => {
    render(<Scoreboard own={OWN} rival={RIVAL} homeId="1008898" score={{}} clock="Q1 10:00" />)
    const [left, right] = sides()
    expect(within(right).getByText(/tu equipo/i)).toBeTruthy()
    expect(within(left).queryByText(/tu equipo/i)).toBeNull()
  })

  it('without a score yet it shows zeros, and our team is on the left when nothing says otherwise', () => {
    render(<Scoreboard own={OWN} rival={RIVAL} homeId={null} score={undefined} clock="Q1 10:00" />)
    const [left, right] = sides()
    expect(within(left).getByText('MIPELLETYMAS B.F. LEON')).toBeTruthy()
    expect(within(left).getByText('0')).toBeTruthy()
    expect(within(right).getByText('0')).toBeTruthy()
  })

  it('shows both logos', () => {
    render(<Scoreboard own={OWN} rival={RIVAL} homeId="1008898" score={{}} clock="Q1 10:00" />)
    expect(screen.getAllByRole('img').map(i => i.getAttribute('src'))).toEqual(['./logos/1008898.png', './logos/1008631.png'])
  })
})
