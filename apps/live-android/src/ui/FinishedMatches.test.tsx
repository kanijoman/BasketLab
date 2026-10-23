import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { FinishedMatch } from '../feed/finishedStore'
import FinishedMatches from './FinishedMatches'

const match = (code: string, title: string, competition?: string): FinishedMatch => ({
  code, title, savedAt: '2026-10-17T20:30:00Z', ownId: '1', alerts: [], plaintext: '{}', game: '{}', ...(competition ? { competition } : {}),
})
const MATCHES = [match('1', 'LEON – UNIBASKET', 'SEGUNDA FEB Liga Regular A'), match('2', 'ZAMORA – LEON', 'TERCERA FEB Liga Regular A-B'), match('3', 'CULTURAL – OVIEDO')]

const onRemove = vi.fn()

function show(matches = MATCHES) {
  render(<FinishedMatches matches={matches} disabled={false} onReview={vi.fn()} onReport={vi.fn()} onRemove={onRemove} reporting={null} error={null} />)
}
const rows = () => Array.from(document.querySelectorAll('.finished-matches li')).map(li => li.textContent ?? '')
const pick = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })

afterEach(cleanup)

describe('FinishedMatches filters (issue #497)', () => {
  it('lists every match, and the team filter has the teams of the titles whichever side they played on', () => {
    show()
    expect(rows()).toHaveLength(3)
    const teams = Array.from((screen.getByLabelText('Equipo') as HTMLSelectElement).options).map(o => o.textContent)
    expect(teams).toEqual(['Todos', 'CULTURAL', 'LEON', 'OVIEDO', 'UNIBASKET', 'ZAMORA'])
  })

  it('filters by team and by competition; the competition narrows the teams', () => {
    show()
    pick('Equipo', 'LEON')
    expect(rows()).toHaveLength(2)
    pick('Competición', 'SEGUNDA FEB Liga Regular A')
    expect(rows()).toHaveLength(1)
    expect(rows()[0]).toContain('UNIBASKET')
    expect((screen.getByLabelText('Equipo') as HTMLSelectElement).value).toBe('LEON')
    pick('Competición', 'TERCERA FEB Liga Regular A-B')
    pick('Equipo', '')
    expect(rows()).toHaveLength(1)
    expect(rows()[0]).toContain('ZAMORA')
  })

  it('without any saved competition (matches of before) there is no competition filter, only the team one', () => {
    show([match('3', 'CULTURAL – OVIEDO'), match('4', 'LEON – ZAMORA')])
    expect(screen.queryByLabelText('Competición')).toBeNull()
    pick('Equipo', 'OVIEDO')
    expect(rows()).toHaveLength(1)
  })

  it('a team that does not play in the newly chosen competition is dropped, and with a single match there are no filters', () => {
    show()
    pick('Equipo', 'UNIBASKET')
    pick('Competición', 'TERCERA FEB Liga Regular A-B')
    expect((screen.getByLabelText('Equipo') as HTMLSelectElement).value).toBe('')
    expect(rows()).toHaveLength(1)
    cleanup()
    show([match('1', 'LEON – UNIBASKET')])
    expect(screen.queryByLabelText('Equipo')).toBeNull()
  })

  it('each match can be deleted, asking first (issue #512)', () => {
    show()
    fireEvent.click(screen.getByRole('button', { name: /eliminar leon – unibasket/i }))
    expect(onRemove).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /sí, eliminar/i }))
    expect(onRemove).toHaveBeenCalledWith('1')
  })
})
