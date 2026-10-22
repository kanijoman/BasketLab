import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { fakeEngine, loadDemo, memoryStore, PKG_TEXT } from './appTestKit'
import { TAB_KEY } from './useTab'

beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})
afterEach(() => vi.useRealTimers())

const openTab = (name: string) => fireEvent.click(screen.getByRole('tab', { name }))

describe('tabs of the app (issue #224)', () => {
  it('opens on the match: score, alerts and the controls, and none of the lists', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    expect(screen.getByRole('tab', { name: 'Partido' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByRole('heading', { name: 'Alertas' })).toBeTruthy()
    expect(screen.getByRole('slider', { name: 'Línea de tiempo' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Próximos partidos' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Paquete de preparación' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Acerca de' })).toBeNull()
  })

  it('has the published matches and the import of a package in the Partidos tab', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    openTab('Partidos')
    expect(screen.getByRole('heading', { name: 'Próximos partidos' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Paquete de preparación' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Alertas' })).toBeNull()
  })

  it('has the About panel in its own tab', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    openTab('Acerca de')
    expect(screen.getByRole('heading', { name: 'Acerca de' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Alertas' })).toBeNull()
  })

  it('remembers the tab for the next time the app opens', async () => {
    const first = render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    openTab('Partidos')
    expect(localStorage.getItem(TAB_KEY)).toBe('paquetes')
    first.unmount()
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    expect(await screen.findByRole('heading', { name: 'Próximos partidos' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Partidos' }).getAttribute('aria-selected')).toBe('true')
  })

  it('keeps the match going and its alerts while another tab is open', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    await waitFor(() => expect(screen.getAllByText(/4 faltas personales/)).toHaveLength(1))
    openTab('Partidos')
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    openTab('Partido')
    expect(screen.getAllByText(/4 faltas personales/)).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Pausa' })).toBeTruthy()
  })

  it('has no demo notice any more: the matches are chosen in the Partidos tab (issue #476)', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    expect(screen.queryByText(/partido de demostración/i)).toBeNull()
    expect(screen.queryByRole('button', { name: /ir a partidos/i })).toBeNull()
  })

  it('has no demo notice once a package is loaded', async () => {
    const store = memoryStore({ plaintext: PKG_TEXT, savedAt: '2026-10-08T12:00:00Z' } as never)
    render(<App engine={fakeEngine()} loadDemo={loadDemo} store={store} />)
    await screen.findByText('EQUIPO PROPIO')
    expect(screen.queryByText(/partido de demostración/i)).toBeNull()
  })
})
