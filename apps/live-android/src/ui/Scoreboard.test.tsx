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

  it('does not label either team as "ours": the app is not only for one club (#322)', () => {
    render(<Scoreboard own={OWN} rival={RIVAL} homeId="1008898" score={{}} clock="Q1 10:00" />)
    expect(screen.queryByText(/tu equipo/i)).toBeNull()
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

  describe('the last text of the feed under the score (issue #490)', () => {
    const LAST = { kind: 'fg3', elapsed: 1500, period: 3, remaining: 252, text: '(RECOLETAS ZAMORA) A. PEREZ: TIRO DE 3 ANOTADO (Puntos: 12)', team_id: '1008898' }

    it('shows the clock and the text of the last line received', () => {
      render(<Scoreboard own={OWN} rival={RIVAL} homeId="1008898" score={{}} clock="Q3 04:12" lastEvent={LAST} />)
      const line = document.querySelector('.last-event') as HTMLElement
      expect(line.textContent).toContain('Q3 04:12')
      expect(line.textContent).toContain('A. PEREZ: TIRO DE 3 ANOTADO')
    })

    it('says nothing before the first line, and does not shout to a screen reader on every line', () => {
      render(<Scoreboard own={OWN} rival={RIVAL} homeId="1008898" score={{}} clock="Q1 10:00" lastEvent={null} />)
      expect(document.querySelector('.last-event')).toBeNull()
      render(<Scoreboard own={OWN} rival={RIVAL} score={{}} clock="Q3 04:12" lastEvent={LAST} />)
      expect(document.querySelector('.last-event')?.getAttribute('aria-live')).toBe('off')
    })

    it('a line without text (an older engine) shows nothing', () => {
      render(<Scoreboard own={OWN} rival={RIVAL} score={{}} clock="Q3 04:12" lastEvent={{ ...LAST, text: '' }} />)
      expect(document.querySelector('.last-event')).toBeNull()
    })

    it('a long text wraps inside the card instead of widening it', () => {
      const css = require('node:fs').readFileSync(require('node:path').join(__dirname, '..', 'styles.css'), 'utf8') as string
      expect(css).toMatch(/\.last-event \{[^}]*overflow-wrap: anywhere/)
    })
  })

  describe('who has the ball (possession indicator)', () => {
    const ball = (team_id: string | null) => ({ team_id, since: 95, why: 'made_basket' })

    it('marks the team that has the ball, only that one, with an accessible label', () => {
      render(<Scoreboard own={OWN} rival={RIVAL} homeId="1008898" score={{}} clock="Q1 10:00" ball={ball('1008631')} />)
      const [left, right] = sides()
      expect(left.classList.contains('has-ball')).toBe(false)
      expect(right.classList.contains('has-ball')).toBe(true)
      expect(within(right).getByLabelText('Tiene el balón: MIPELLETYMAS B.F. LEON')).toBeTruthy()
      expect(screen.getAllByLabelText(/Tiene el balón/)).toHaveLength(1)
    })

    it('marks nobody when the ball is loose, unknown or the id is not one of the teams', () => {
      for (const b of [ball(null), null, undefined, ball('999')]) {
        const { unmount } = render(<Scoreboard own={OWN} rival={RIVAL} homeId="1008898" score={{}} clock="Q1 10:00" ball={b} />)
        expect(document.querySelectorAll('.has-ball')).toHaveLength(0)
        unmount()
      }
    })
  })
})
