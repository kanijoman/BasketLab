import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import DemoControls, { SAMPLE, SPEEDS } from './DemoControls'

const HOME = { id: '1', name: 'RECOLETAS ZAMORA' }
const AWAY = { id: '2', name: 'MIPELLETYMAS B.F. LEON' }
const SOURCES = [{ value: '2524470', label: 'Zamora – León' }, { value: SAMPLE, label: 'Partido de ejemplo' }]

function setup(over: Partial<Parameters<typeof DemoControls>[0]> = {}) {
  const props = {
    source: '2524470', sources: SOURCES, onSource: vi.fn(), playing: false, onPlay: vi.fn(), finished: false, speed: 1, onSpeed: vi.fn(),
    onRestart: vi.fn(), onSeek: vi.fn(), ms: null, feed: 'ok' as const, elapsed: 65, duration: 7150, home: HOME, away: AWAY, ...over,
  }
  render(<DemoControls {...props} />)
  return props
}

describe('transport bar (issue #231)', () => {
  it('has the match selector in its own row, with the crests of both teams', () => {
    setup()
    const row = screen.getByLabelText('Partido de la demostración').closest('.transport-source') as HTMLElement
    expect(row).toBeTruthy()
    expect(within(row).getByAltText(HOME.name)).toBeTruthy()
    expect(within(row).getByAltText(AWAY.name)).toBeTruthy()
  })

  it('changes the match from the selector', () => {
    const p = setup()
    fireEvent.change(screen.getByLabelText('Partido de la demostración'), { target: { value: SAMPLE } })
    expect(p.onSource).toHaveBeenCalledWith(SAMPLE)
  })

  it('has play/pause and restart as icon buttons with an accessible name', () => {
    const p = setup()
    const play = screen.getByRole('button', { name: 'Reproducir' })
    expect(play.querySelector('svg')).toBeTruthy()
    fireEvent.click(play)
    expect(p.onPlay).toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Reiniciar' }))
    expect(p.onRestart).toHaveBeenCalled()
  })

  it('says Pausa while playing', () => {
    setup({ playing: true })
    expect(screen.getByRole('button', { name: 'Pausa' })).toBeTruthy()
  })

  it('disables play at the end of the game', () => {
    setup({ finished: true })
    expect((screen.getByRole('button', { name: 'Reproducir' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('has the speed as a segmented control with the chosen one marked', () => {
    const p = setup({ speed: 30 })
    const group = screen.getByRole('radiogroup', { name: 'Velocidad' })
    const radios = within(group).getAllByRole('radio')
    expect(radios.map(r => r.textContent)).toEqual(SPEEDS.map(s => `${s}×`))
    expect(radios.map(r => r.getAttribute('aria-checked'))).toEqual(['false', 'false', 'true', 'false', 'false'])
    fireEvent.click(within(group).getByRole('radio', { name: '300×' }))
    expect(p.onSpeed).toHaveBeenCalledWith(300)
  })

  it('has a timeline with the elapsed and the total time that seeks when moved', () => {
    const p = setup()
    const slider = screen.getByRole('slider', { name: 'Línea de tiempo' }) as HTMLInputElement
    expect(slider.min).toBe('0')
    expect(slider.max).toBe('7150')
    expect(slider.value).toBe('65')
    expect(screen.getByText('1:05 / 119:10')).toBeTruthy()
    fireEvent.change(slider, { target: { value: '3000' } })
    expect(p.onSeek).toHaveBeenCalledWith(3000)
  })

  it('also has the timeline for the sample game', () => {
    setup({ source: SAMPLE })
    expect(screen.getByRole('slider', { name: 'Línea de tiempo' })).toBeTruthy()
  })

  it('has a disabled timeline until the duration is known', () => {
    setup({ duration: null })
    expect((screen.getByRole('slider', { name: 'Línea de tiempo' }) as HTMLInputElement).disabled).toBe(true)
  })

  it('shows the state of the recorded feed under the timeline and the engine time', () => {
    setup({ feed: 'waiting', ms: 23 })
    expect(screen.getByText(/esperando el inicio del partido/i)).toBeTruthy()
    expect(screen.getByText('23 ms')).toBeTruthy()
  })

  it('says when FEB does not answer', () => {
    setup({ feed: 'gap' })
    expect(screen.getByText(/FEB no responde \(404\)/)).toBeTruthy()
  })

  it('shows no feed state for the sample game', () => {
    setup({ source: SAMPLE, feed: 'gap' })
    expect(screen.queryByText(/FEB no responde/)).toBeNull()
  })
})
