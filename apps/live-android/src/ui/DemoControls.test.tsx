import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import DemoControls, { SAMPLE, SPEEDS } from './DemoControls'

const HOME = { id: '1', name: 'RECOLETAS ZAMORA' }
const AWAY = { id: '2', name: 'MIPELLETYMAS B.F. LEON' }

function setup(over: Partial<Parameters<typeof DemoControls>[0]> = {}) {
  const props = {
    source: '2524470', title: 'Recoletas Zamora – Mipelletymas B.F. Leon', playing: false, onPlay: vi.fn(), finished: false, speed: 1, onSpeed: vi.fn(),
    onRestart: vi.fn(), onSeek: vi.fn(), ms: null, feed: 'ok' as const, elapsed: 65, duration: 7150, home: HOME, away: AWAY, ...over,
  }
  render(<DemoControls {...props} />)
  return props
}

describe('transport bar (issue #231)', () => {
  it('has the match title in its own row, with the crests of both teams', () => {
    setup()
    const row = screen.getByLabelText('Partido de la demostración').closest('.transport-source') as HTMLElement
    expect(row).toBeTruthy()
    expect(within(row).getByAltText(HOME.name)).toBeTruthy()
    expect(within(row).getByAltText(AWAY.name)).toBeTruthy()
  })

  it('shows the name of the match and has no selector: the matches are chosen in the Partidos tab (issue #476)', () => {
    setup()
    expect(screen.getByLabelText('Partido de la demostración').textContent).toContain('Recoletas Zamora')
    expect(document.querySelector('select')).toBeNull()
  })

  it('has play/pause and restart as icon buttons with an accessible name', () => {
    const p = setup({ elapsed: 0 })
    const play = screen.getByRole('button', { name: 'Reproducir' })
    expect(play.querySelector('svg')).toBeTruthy()
    fireEvent.click(play)
    expect(p.onPlay).toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Reiniciar' }))
    expect(p.onRestart).toHaveBeenCalled()      // nothing to lose at the very start: no question asked
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

  it('has a timeline with the elapsed and the total time', () => {
    setup()
    const slider = screen.getByRole('slider', { name: 'Línea de tiempo' }) as HTMLInputElement
    expect(slider.min).toBe('0')
    expect(slider.max).toBe('7150')
    expect(slider.value).toBe('65')
    expect(screen.getByText('1:05 / 119:10')).toBeTruthy()
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

describe('no accidental resets (issue #309)', () => {
  const slider = () => screen.getByRole('slider', { name: 'Línea de tiempo' }) as HTMLInputElement
  const drag = (to: number) => fireEvent.change(slider(), { target: { value: String(to) } })
  const release = () => fireEvent.pointerUp(slider())

  it('restarting a match in progress asks first, and only a yes restarts it', () => {
    const p = setup({ elapsed: 600 })
    fireEvent.click(screen.getByRole('button', { name: 'Reiniciar' }))
    const ask = screen.getByRole('group', { name: 'Confirmar' })
    expect(within(ask).getByText(/se perderán las alertas/i)).toBeTruthy()
    expect(ask.textContent).not.toMatch(/respuestas/i)      // the feedback answers are kept (see #314): do not promise they are lost
    expect(p.onRestart).not.toHaveBeenCalled()
    fireEvent.click(within(ask).getByRole('button', { name: /sí, reiniciar/i }))
    expect(p.onRestart).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('group', { name: 'Confirmar' })).toBeNull()
  })

  it('cancelling the question leaves everything as it was', () => {
    const p = setup({ elapsed: 600 })
    fireEvent.click(screen.getByRole('button', { name: 'Reiniciar' }))
    fireEvent.click(screen.getByRole('button', { name: /cancelar/i }))
    expect(p.onRestart).not.toHaveBeenCalled()
    expect(screen.queryByRole('group', { name: 'Confirmar' })).toBeNull()
  })

  it('moving the timeline does not seek until it is released (a touch while scrolling must not jump)', () => {
    const p = setup({ elapsed: 600 })
    drag(630)
    expect(slider().value).toBe('630')      // it follows the finger
    expect(p.onSeek).not.toHaveBeenCalled()
    release()
    expect(p.onSeek).toHaveBeenCalledWith(630)
  })

  it('after cancelling a jump the bar goes back to the playback position even if the device sent a late change (#472 regression)', () => {
    setup({ elapsed: 600 })
    drag(100); release()
    drag(105)                                    // a late input event after the release (seen on the tablet): it must not leave the thumb behind
    fireEvent.click(screen.getByRole('button', { name: /cancelar/i }))
    expect(slider().value).toBe('600')
    slider().value = '3000'                      // the browser moved the thumb without telling React
    fireEvent.pointerCancel(slider())
    expect(slider().value).toBe('600')
  })

  it('a small jump forward is direct; a jump back or a long one forward asks first', () => {
    const p = setup({ elapsed: 600 })
    drag(700); release()
    expect(p.onSeek).toHaveBeenCalledWith(700)
    vi.mocked(p.onSeek).mockClear()
    drag(100); release()
    expect(p.onSeek).not.toHaveBeenCalled()
    expect(screen.getByText(/saltar a 1:40/i)).toBeTruthy()
    expect(screen.getByText(/volver atrás borra las alertas/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^saltar$/i }))
    expect(p.onSeek).toHaveBeenCalledWith(100)
  })

  it('a long jump forward says that the alerts in between are not shown', () => {
    const p = setup({ elapsed: 600 })
    drag(3000); release()
    expect(screen.getByText(/saltar a 50:00/i)).toBeTruthy()
    expect(screen.getByText(/no se muestran las alertas del tramo/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /cancelar/i }))
    expect(p.onSeek).not.toHaveBeenCalled()
    expect(slider().value).toBe('600')      // the bar goes back to where the match is
  })

  it('the keyboard commits when the key is released', () => {
    const p = setup({ elapsed: 600 })
    drag(610)
    fireEvent.keyUp(slider(), { key: 'ArrowRight' })
    expect(p.onSeek).toHaveBeenCalledWith(610)
  })
})
