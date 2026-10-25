import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { FinishedMatch } from '../feed/finishedStore'
import FinishedMatches from './FinishedMatches'
import { optionLabels, pickOption, valueOf } from '../test/select'

const match = (code: string, title: string, competition?: string): FinishedMatch => ({
  code, title, savedAt: '2026-10-17T20:30:00Z', ownId: '1', alerts: [], plaintext: '{}', game: '{}', ...(competition ? { competition } : {}),
})
const MATCHES = [match('1', 'LEON – UNIBASKET', 'SEGUNDA FEB Liga Regular A'), match('2', 'ZAMORA – LEON', 'TERCERA FEB Liga Regular A-B'), match('3', 'CULTURAL – OVIEDO')]

const onRemove = vi.fn()

function show(matches = MATCHES) {
  render(<FinishedMatches matches={matches} disabled={false} onReview={vi.fn()} onReport={vi.fn()} onRemove={onRemove} reporting={null} error={null} />)
}
const rows = () => Array.from(document.querySelectorAll('.finished-matches li')).map(li => li.textContent ?? '')
const pick = pickOption

afterEach(cleanup)

describe('FinishedMatches filters (issue #497)', () => {
  it('lists every match, and the team filter has the teams of the titles whichever side they played on', () => {
    show()
    expect(rows()).toHaveLength(3)
    expect(optionLabels('Equipo')).toEqual(['Todos', 'CULTURAL', 'LEON', 'OVIEDO', 'UNIBASKET', 'ZAMORA'])
  })

  it('filters by team and by competition; the competition narrows the teams', () => {
    show()
    pick('Equipo', 'LEON')
    expect(rows()).toHaveLength(2)
    pick('Competición', 'SEGUNDA FEB Liga Regular A')
    expect(rows()).toHaveLength(1)
    expect(rows()[0]).toContain('UNIBASKET')
    expect(valueOf('Equipo')).toBe('LEON')
    pick('Competición', 'TERCERA FEB Liga Regular A-B')
    pick('Equipo', '')
    expect(rows()).toHaveLength(1)
    expect(rows()[0]).toContain('ZAMORA')
  })

  it('without any saved competition (matches of before) there is no competition filter, only the team one', () => {
    show([match('3', 'CULTURAL – OVIEDO'), match('4', 'LEON – ZAMORA')])
    expect(screen.queryByRole('combobox', { name: 'Competición' })).toBeNull()
    pick('Equipo', 'OVIEDO')
    expect(rows()).toHaveLength(1)
  })

  it('a team that does not play in the newly chosen competition is dropped, and with a single match there are no filters', () => {
    show()
    pick('Equipo', 'UNIBASKET')
    pick('Competición', 'TERCERA FEB Liga Regular A-B')
    expect(valueOf('Equipo')).toBe('')
    expect(rows()).toHaveLength(1)
    cleanup()
    show([match('1', 'LEON – UNIBASKET')])
    expect(screen.queryByRole('combobox', { name: 'Equipo' })).toBeNull()
  })

  it('each match can be deleted, asking first (issue #512)', () => {
    show()
    fireEvent.click(screen.getByRole('button', { name: /eliminar leon – unibasket/i }))
    expect(onRemove).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /sí, eliminar/i }))
    expect(onRemove).toHaveBeenCalledWith('1')
  })
})

describe('FinishedMatches incomplete (issue #556)', () => {
  it('says which matches were kept before their end, and only those', () => {
    show([{ ...match('1', 'LEON – UNIBASKET'), complete: false }, { ...match('2', 'ZAMORA – LEON'), complete: true }, match('3', 'CULTURAL – OVIEDO')])
    const tagged = rows().filter(r => /incompleto/i.test(r))
    expect(tagged).toHaveLength(1)
    expect(tagged[0]).toContain('UNIBASKET')
  })
})

describe('FinishedMatches buttons (issue #570)', () => {
  it('say what they do without repeating the teams: Revisar, Informe and Eliminar (the names for a screen reader keep the match)', () => {
    show([match('1', 'LEON – UNIBASKET')])
    const row = document.querySelector('.finished-matches li') as HTMLElement
    expect(Array.from(row.querySelectorAll('button')).map(b => b.textContent)).toEqual(['Revisar', 'Informe', 'Eliminar'])
    expect(screen.getByRole('button', { name: 'Revisar LEON – UNIBASKET' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Informe PDF de LEON – UNIBASKET' })).toBeTruthy()
  })
})
