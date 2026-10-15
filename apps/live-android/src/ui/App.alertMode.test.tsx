// Issue #130: the alert mode is chosen in Acerca de, reaches the engine, and is written in the session log.
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { fakeEngine, loadDemo } from './appTestKit'
import { ALERT_MODE_KEY } from './useAlertMode'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})

async function openAbout(engine = fakeEngine()) {
  render(<App engine={engine} loadDemo={loadDemo} />)
  await screen.findByText('EQUIPO PROPIO')
  fireEvent.click(screen.getByRole('tab', { name: 'Acerca de' }))
  return engine
}

describe('alert mode in Acerca de (issue #130)', () => {
  it('shows the three modes with the medium one chosen, each with what it does', async () => {
    await openAbout()
    const group = screen.getByRole('radiogroup', { name: 'Modo de alertas' })
    expect(group.querySelectorAll('input[type=radio]')).toHaveLength(3)
    expect((screen.getByRole('radio', { name: /Medio/ }) as HTMLInputElement).checked).toBe(true)
    expect(screen.getByText(/más avisos y antes/i)).toBeTruthy()
    expect(screen.getByText(/solo lo que está claro/i)).toBeTruthy()
  })

  it('choosing a mode tells the engine, is remembered and goes to the session log', async () => {
    const engine = await openAbout()
    fireEvent.click(screen.getByRole('radio', { name: /Conservador/ }))
    await waitFor(() => expect(engine.setMode).toHaveBeenLastCalledWith('conservative'))
    expect(localStorage.getItem(ALERT_MODE_KEY)).toBe('conservative')
    expect(await screen.findByText(/modo de alertas: conservador/i)).toBeTruthy()
  })

  it('the engine gets the remembered mode before the first package starts', async () => {
    localStorage.setItem(ALERT_MODE_KEY, 'aggressive')
    const engine = fakeEngine()
    render(<App engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    const mode = (engine.setMode as ReturnType<typeof vi.fn>).mock.invocationCallOrder[0]
    const start = (engine.start as ReturnType<typeof vi.fn>).mock.invocationCallOrder[0]
    expect((engine.setMode as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe('aggressive')
    expect(mode).toBeLessThan(start)
  })
})
