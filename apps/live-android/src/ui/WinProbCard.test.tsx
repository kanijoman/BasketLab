import { act, render, renderHook, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import WinProbCard from './WinProbCard'
import { useExperimental, EXPERIMENTAL_KEY } from './useExperimental'
import { useWinProbHistory } from './useWinProbHistory'
import type { EngineOutput, WinLever, WinProb } from '../engine/types'

const OWN = { id: '1', name: 'EQUIPO PROPIO' }
const WP: WinProb = { p: 0.6372, projected_margin: 4.25, sd: 9.1, poss_remaining: 40.2, mu_per_100: 3.1, reliable: true }
const LEVERS: WinLever[] = [
  { id: 'orb', gain: 0.062, gain_pts: 2.1, proposal: [{ type: 'sub', in_name: 'B', out_name: 'A', message: 'Entra B por A y mejora el rebote ofensivo (+0.8 σ)' }] },
  { id: 'pace', direction: 'down', gain: 0.031, gain_pts: -0.4 },
  { id: 'tov', gain: 0.018, gain_pts: 0.9, proposal: [] },
  { id: 'efg', gain: 0.012, gain_pts: 0.5 },
]

afterEach(() => vi.restoreAllMocks())

describe('WinProbCard (issue #257, experimental)', () => {
  it('shows the probability of the own team as a rounded percentage, marked as experimental', () => {
    render(<WinProbCard winProb={WP} levers={[]} own={OWN} history={[]} />)
    expect(screen.getByText('64 %')).toBeTruthy()
    expect(screen.getByText(/experimental/i, { selector: '.badge' })).toBeTruthy()
    expect(screen.getByText(/margen proyectado: \+4,3/i)).toBeTruthy()
    expect(screen.getByText(/entre el 30 % y el 70 % puede desviarse unos ±7 puntos/i)).toBeTruthy()
  })

  it('lists the three main levers as a diagnosis, with the first proposal and no promised gain (#567)', () => {
    render(<WinProbCard winProb={WP} levers={LEVERS} own={OWN} history={[]} />)
    expect(screen.getByRole('heading', { name: /dónde se pierden puntos/i })).toBeTruthy()
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0].textContent).toMatch(/rebote ofensivo/i)
    expect(items.map(li => li.textContent).join(' ')).not.toMatch(/\+\d+ ?%/)       // the study found no effect on the probability: no «+6 %»
    expect(items[0].textContent).toMatch(/entra b por a/i)
    expect(items[1].textContent).toMatch(/bajar el ritmo/i)
    expect(items[2].textContent).toMatch(/pérdidas/i)
    expect(screen.queryByText(/acierto de tiro/i)).toBeNull()
  })

  it('says whether a factor lever is in the attack or in the defence when the engine knows it (#586)', () => {
    render(<WinProbCard winProb={WP} levers={[{ id: 'efg', side: 'defence', gain: 0.05, gain_pts: 1 }, { id: 'tov', side: 'both', gain: 0.04, gain_pts: 1 }, { id: 'orb', side: 'attack', gain: 0.03, gain_pts: 1 }]} own={OWN} history={[]} />)
    const items = screen.getAllByRole('listitem').map(li => li.textContent)
    expect(items[0]).toMatch(/acierto de tiro \(defensa\)/i)
    expect(items[1]).toMatch(/pérdidas \(ataque y defensa\)/i)
    expect(items[2]).toMatch(/rebote ofensivo \(ataque\)/i)
  })

  it('a faster pace is said as such', () => {
    render(<WinProbCard winProb={WP} levers={[{ id: 'pace', direction: 'up', gain: 0.02, gain_pts: 0.3 }]} own={OWN} history={[]} />)
    expect(screen.getByText(/subir el ritmo/i)).toBeTruthy()
  })

  it('says when the game does not tell much yet', () => {
    render(<WinProbCard winProb={{ ...WP, reliable: false }} levers={[]} own={OWN} history={[]} />)
    expect(screen.getByText(/basada en el valor previo y el marcador/i)).toBeTruthy()
  })

  it('draws the evolution once there are two points', () => {
    const { rerender } = render(<WinProbCard winProb={WP} levers={[]} own={OWN} history={[{ t: 60, p: 0.5 }]} />)
    expect(screen.queryByRole('img', { name: /evolución/i })).toBeNull()
    rerender(<WinProbCard winProb={WP} levers={[]} own={OWN} history={[{ t: 60, p: 0.5 }, { t: 600, p: 0.64 }]} />)
    expect(screen.getByRole('img', { name: /evolución/i })).toBeTruthy()
  })

  it('without a probability it renders nothing', () => {
    const { container } = render(<WinProbCard winProb={undefined} levers={undefined} own={OWN} history={[]} />)
    expect(container.innerHTML).toBe('')
  })
})

const output = (elapsed: number, p?: number): EngineOutput => ({
  snapshot: { elapsed } as never, alerts: [],
  analysis: p === undefined ? {} : { win_prob: { ...WP, p } },
})

describe('useWinProbHistory', () => {
  it('keeps one point per engine output with a probability and starts again with a new match or a jump back', () => {
    const { result, rerender } = renderHook(({ out }) => useWinProbHistory(out), { initialProps: { out: null as EngineOutput | null } })
    expect(result.current).toEqual([])
    rerender({ out: output(60, 0.5) })
    rerender({ out: output(120, 0.55) })
    rerender({ out: output(120, 0.55) })      // the same moment again: not a new point
    rerender({ out: output(180) })            // no probability in this output
    expect(result.current).toEqual([{ t: 60, p: 0.5 }, { t: 120, p: 0.55 }])
    rerender({ out: output(30, 0.4) })        // the timeline went back
    expect(result.current).toEqual([{ t: 30, p: 0.4 }])
    rerender({ out: null })                   // new match
    expect(result.current).toEqual([])
  })
})

describe('useExperimental', () => {
  it('is on by default and remembers being switched off', () => {
    const first = renderHook(() => useExperimental('win_prob'))
    expect(first.result.current[0]).toBe(true)
    act(() => first.result.current[1](false))
    expect(first.result.current[0]).toBe(false)
    expect(localStorage.getItem(`${EXPERIMENTAL_KEY}:win_prob`)).toBe('off')
    const again = renderHook(() => useExperimental('win_prob'))
    expect(again.result.current[0]).toBe(false)
  })

  it('with blocked storage it still works for the session', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    const { result } = renderHook(() => useExperimental('win_prob'))
    expect(result.current[0]).toBe(true)
    act(() => result.current[1](false))
    expect(result.current[0]).toBe(false)
  })

  // #405: only the value is shown; the rest is collapsible
  it('shows only the percentage and keeps the margin, the chart and the levers collapsed', () => {
    const { container } = render(<WinProbCard winProb={WP} levers={LEVERS} own={OWN} history={[{ t: 0, p: 0.5 }, { t: 600, p: 0.6 }]} />)
    const details = container.querySelector('details') as HTMLDetailsElement
    expect(details.open).toBe(false)
    expect(details.contains(screen.getByText('64 %'))).toBe(false)
    expect(details.contains(screen.getByText(/margen proyectado/i))).toBe(true)
    expect(details.contains(screen.getByText(/dónde se pierden puntos/i))).toBe(true)
    expect(details.contains(screen.getByRole('img', { name: /evolución/i }))).toBe(true)
    expect(details.contains(screen.getByText(/puede desviarse/i))).toBe(true)
  })
})
