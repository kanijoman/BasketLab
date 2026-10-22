import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DemoMatch } from '../engine/demo'
import MatchLibrary from './MatchLibrary'

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
    expect(rows()[1]).toContain('SEGUNDA FEB · Liga Regular A —')
    expect(rows()[rows().length - 1]).toContain('Partido de ejemplo')
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
})
