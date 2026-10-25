import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DemoMatch } from '../engine/demo'
import MatchLibrary from './MatchLibrary'
import { optionLabels, pickOption, valueOf } from '../test/select'

const demo = (code: string, over: Partial<DemoMatch> = {}): DemoMatch => ({
  code, title: `Equipo ${code} – Rival ${code}`, date: '2026-10-18T18:30', home: { id: `h${code}`, name: `EQUIPO ${code}` }, away: { id: `a${code}`, name: `RIVAL ${code}` },
  recording: `${code}.recording.json`, package: `${code}.package.json`, ...over,
})
const DEMOS = [demo('2524470', { title: 'Recoletas Zamora – Mipelletymas B.F. Leon' }), demo('2536133', { competition: 'SEGUNDA FEB · Liga Regular A', teamId: '1008857' }),
  demo('2536851', { competition: 'TERCERA FEB · Liga Regular A-B', teamId: '1010490' })]

function show(over: Partial<React.ComponentProps<typeof MatchLibrary>> = {}) {
  const props = { demos: DEMOS, favorites: [], hasSample: true, source: '2524470', disabled: false, onView: vi.fn(), reporting: null, onReport: vi.fn(), error: null, ...over }
  render(<MatchLibrary {...props} />)
  return props
}
const rows = () => Array.from(document.querySelectorAll('.match-library li')).map(li => li.textContent ?? '')

afterEach(cleanup)

describe('MatchLibrary: the demos of the Partidos tab (issues #476, #477, feedback of 0.3.2)', () => {
  it('lists every demo with its competition and the sample game last', () => {
    show()
    expect(rows()[0]).toContain('Recoletas Zamora')
    expect(rows()[1]).toContain('SEGUNDA FEB · Liga Regular A')
    expect(rows()[rows().length - 1]).toContain('Partido de ejemplo')
  })

  it('each row has its text and then its buttons, with the competition in its own line (issue #507)', () => {
    show()
    const row = document.querySelector('.match-library li')!
    expect(row.children[0].classList.contains('round-info') && row.children[1].classList.contains('round-sides')).toBe(true)
    const second = document.querySelectorAll('.match-library li')[1]
    expect(second.querySelector('.round-info')!.firstElementChild?.classList.contains('round-competition')).toBe(true)
    expect(second.querySelector('.match-title')?.textContent).toContain('Equipo 2536133')
  })

  it('the demos of a team of interest come first', () => {
    show({ favorites: [{ teamId: '1010490', name: 'CAJA RURAL RDL' }] })
    expect(rows()[0]).toContain('TERCERA FEB')
  })

  it('«Ver» opens that match and says which one is open now', () => {
    const p = show()
    fireEvent.click(screen.getByRole('button', { name: /ver segunda feb · liga regular a/i }))
    expect(p.onView).toHaveBeenCalledWith('2536133')
    expect((screen.getByRole('button', { name: /ver recoletas zamora/i }) as HTMLButtonElement).disabled).toBe(true)     // the one that is open
    expect(within(document.querySelector('.match-library li')! as HTMLElement).getByText(/viendo/i)).toBeTruthy()
  })

  it('every match has its PDF report, also the sample game (issue #477)', () => {
    const p = show()
    fireEvent.click(screen.getByRole('button', { name: /informe pdf de segunda feb/i }))
    expect(p.onReport).toHaveBeenCalledWith('2536133')
    fireEvent.click(screen.getByRole('button', { name: /informe pdf de partido de ejemplo/i }))
    expect(p.onReport).toHaveBeenCalledWith('sample')
  })

  it('while a report is being built its button says so and the others wait', () => {
    show({ reporting: '2536133' })
    expect(screen.getByRole('button', { name: /informe pdf de segunda feb/i }).textContent).toMatch(/generando/i)
    expect((screen.getByRole('button', { name: /informe pdf de recoletas/i }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('with a live connection running nothing can be opened and it says why', () => {
    show({ disabled: true })
    expect((screen.getByRole('button', { name: /ver segunda feb/i }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/desconecta antes/i)).toBeTruthy()
  })

  it('shows the error of a report', () => {
    show({ error: 'No se pudo generar el informe: x' })
    expect(screen.getByRole('alert').textContent).toContain('No se pudo generar')
  })

  it('without demos and without the sample game it shows nothing', () => {
    show({ demos: [], hasSample: false })
    expect(document.querySelector('.match-library')).toBeNull()
  })

  describe('filters by competition and team', () => {
    const pick = pickOption

    it('narrows the list to a competition and its teams, and the sample game is not part of a filtered list', () => {
      show()
      pick('Competición', 'SEGUNDA FEB · Liga Regular A')
      expect(rows()).toHaveLength(1)
      expect(rows()[0]).toContain('SEGUNDA FEB')
      const teams = optionLabels('Equipo')
      expect(teams).toEqual(['Todos', 'EQUIPO 2536133', 'RIVAL 2536133'])
    })

    it('filters by team, whichever side it plays on, and «Todas» brings everything back', () => {
      show()
      pick('Equipo', 'RIVAL 2536851')
      expect(rows()).toHaveLength(1)
      expect(rows()[0]).toContain('TERCERA FEB')
      pick('Equipo', '')
      expect(rows()).toHaveLength(4)
    })

    it('changing the competition drops a team that does not play in it', () => {
      show()
      pick('Equipo', 'RIVAL 2536851')
      pick('Competición', 'SEGUNDA FEB · Liga Regular A')
      expect(valueOf('Equipo')).toBe('')
      expect(rows()).toHaveLength(1)
    })

    it('says so when nothing matches, and has no competition filter when the manifest has none', () => {
      show({ demos: [demo('1')], hasSample: false })
      expect(screen.queryByRole('combobox', { name: 'Competición' })).toBeNull()
      pick('Equipo', 'EQUIPO 1')
      expect(rows()).toHaveLength(1)
    })
  })
})
