import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { fakeEngine, loadDemo } from './appTestKit'
import { BEAT_KEY, LOG_KEY, readSession } from './sessionLog'

beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})
afterEach(() => vi.useRealTimers())

const texts = () => readSession().map(e => e.text)

async function play(ms = 3000) {
  render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
  await screen.findByText('EQUIPO PROPIO')
  fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
  await act(async () => { await vi.advanceTimersByTimeAsync(ms) })
}

describe('session log of the app (issue #309)', () => {
  it('logs the start of the app and beats while it is open', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    expect(texts()).toContain('Arranque de la app')
    const first = localStorage.getItem(BEAT_KEY)
    await act(async () => { await vi.advanceTimersByTimeAsync(12_000) })
    expect(localStorage.getItem(BEAT_KEY)).not.toBe(first)
  })

  it('notes a start soon after the app was alive as a restart nobody asked for', async () => {
    localStorage.setItem(BEAT_KEY, String(Date.now() - 4_000))
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    expect(texts().some(t => /reinicio no pedido/i.test(t))).toBe(true)
  })

  it('shows the log in Acerca de', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('tab', { name: 'Acerca de' }))
    const block = screen.getByRole('region', { name: 'Registro de la sesión' })
    expect(block.textContent).toMatch(/arranque de la app/i)
  })

  it('logs a restart only once the user confirms it', async () => {
    await play()
    fireEvent.click(screen.getByRole('button', { name: 'Reiniciar' }))
    expect(texts().some(t => /reiniciado/i.test(t))).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: /sí, reiniciar/i }))
    await waitFor(() => expect(texts().some(t => /partido reiniciado con el botón reiniciar/i.test(t))).toBe(true))
  })

  it('logs a confirmed jump of the timeline', async () => {
    await play()
    const slider = screen.getByRole('slider', { name: 'Línea de tiempo' })
    fireEvent.change(slider, { target: { value: '0' } })
    fireEvent.pointerUp(slider)
    fireEvent.click(screen.getByRole('button', { name: /^saltar$/i }))
    await waitFor(() => expect(texts().some(t => /salto en la línea de tiempo a 0:00/i.test(t))).toBe(true))
  })

  it('the diagnostics copied from Acerca de carry the log', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText }, userAgent: 'UA' })
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('tab', { name: 'Acerca de' }))
    fireEvent.click(screen.getByRole('button', { name: /copiar diagnóstico/i }))
    await waitFor(() => expect(writeText).toHaveBeenCalled())
    expect(writeText.mock.calls[0][0]).toMatch(/Registro reciente/)
    expect(writeText.mock.calls[0][0]).toMatch(/Arranque de la app/)
    expect(localStorage.getItem(LOG_KEY)).toBeTruthy()
  })
})
