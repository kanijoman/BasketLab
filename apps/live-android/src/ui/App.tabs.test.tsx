import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { fakeEngine, loadDemo, memoryStore, PKG_TEXT } from './appTestKit'
import { optionLabels, pickOption, valueOf } from '../test/select'

beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})
afterEach(() => vi.useRealTimers())

const openTab = (name: string) => fireEvent.click(screen.getByRole('tab', { name }))

const RECORDED = {
  code: '1', title: 'Local – Visitante', date: '2026-10-10T17:00', home: { id: '2', name: 'LOCAL' }, away: { id: '1', name: 'VISITANTE' },
  recording: '1.recording.json', package: '1.package.json',
}

describe('tabs of the app (issue #224)', () => {
  it('opens on the match: score, alerts and the controls, and none of the lists', async () => {
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    expect(screen.getByRole('tab', { name: 'Partido' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByRole('heading', { name: 'Alertas' })).toBeTruthy()
    expect(screen.getByRole('slider', { name: 'Línea de tiempo' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Próximos partidos' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Paquete de preparación' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Acerca de' })).toBeNull()
  })

  it('has the published matches and the import of a package in the Partidos tab', async () => {
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    openTab('Partidos')
    expect(screen.getByRole('heading', { name: 'Próximos partidos' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Paquete de preparación' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Alertas' })).toBeNull()
  })

  it('has the About panel in its own tab', async () => {
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    openTab('Acerca de')
    expect(screen.getByRole('heading', { name: 'Acerca de' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Alertas' })).toBeNull()
  })

  it('always opens on the list of matches, and a chosen match takes the user to the Partido tab', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} loadManifest={() => Promise.resolve([RECORDED])} loadMatch={() => Promise.resolve({ package: 'PKG', recording: 'REC' })} />)
    expect(await screen.findByRole('heading', { name: 'Próximos partidos' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Partidos' }).getAttribute('aria-selected')).toBe('true')
    pickOption('Tipo de partido', 'demo')
    await waitFor(() => expect((screen.getByRole('button', { name: /ver partido de ejemplo/i }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: /ver partido de ejemplo/i }))
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Partido' }).getAttribute('aria-selected')).toBe('true'))
  })

  describe('the kind of match is chosen with a selector in Partidos', () => {
    const open = async () => {
      render(<App engine={fakeEngine()} loadDemo={loadDemo} loadManifest={() => Promise.resolve([RECORDED])} loadMatch={() => Promise.resolve({ package: 'PKG', recording: 'REC' })} />)
      return screen.findByRole('combobox', { name: 'Tipo de partido' })
    }

    it('starts on the live matches and offers live, demos and finished matches', async () => {
      const kind = await open()
      expect(kind.getAttribute('data-value')).toBe('live')
      expect(optionLabels('Tipo de partido')).toEqual(['En directo', 'Demos', 'Finalizados'])
      expect(screen.getByRole('heading', { name: 'Próximos partidos' })).toBeTruthy()
      expect(screen.queryByRole('region', { name: 'Partidos de demostración' })).toBeNull()
    })

    it('«Demos» shows the list of demos with its filters, and not the live packages', async () => {
      await open()
      pickOption('Tipo de partido', 'demo')
      expect(screen.getByRole('region', { name: 'Partidos de demostración' })).toBeTruthy()
      expect(screen.getByRole('combobox', { name: 'Equipo' })).toBeTruthy()
      expect(screen.queryByRole('heading', { name: 'Próximos partidos' })).toBeNull()
    })

    it('«Finalizados» says there are none yet instead of showing an empty page', async () => {
      await open()
      pickOption('Tipo de partido', 'finished')
      expect(screen.getByText(/todavía no hay partidos finalizados/i)).toBeTruthy()
    })

    it('the choice is kept when the user goes to another tab and comes back', async () => {
      await open()
      pickOption('Tipo de partido', 'demo')
      openTab('Acerca de')
      openTab('Partidos')
      expect(valueOf('Tipo de partido')).toBe('demo')
    })
  })

  it('keeps the match going and its alerts while another tab is open', async () => {
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} />)
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

  describe('the Boxscore tab (issue #593)', () => {
    const player = (name: string, team: string, over = {}) => ({ name, team_id: team, on_court: true, minutes: 600, pf: 0, pts: 0, pm: 0, fd: 0, stats: { fg2m: 0, fg2a: 0, fg3m: 0, fg3a: 0, ftm: 0, fta: 0, orb: 0, drb: 0, tov: 0, stl: 0, ast: 0, blk: 0 }, ...over })
    const withBoxscore = fakeEngine({
      replay: vi.fn(async (e: number) => ({
        snapshot: { period: 1, remaining: 600 - e, elapsed: e, score: { '1': 2, '2': 0 }, home_id: '1', teams: { '1': { name: 'EQUIPO PROPIO', fouls_game: 0 }, '2': { name: 'EQUIPO RIVAL', fouls_game: 0 } },
          players: { p1: player('A. PROPIA', '1', { pts: 2 }), r1: player('R. RIVAL', '2') }, last_stat: { seq: e, player_id: 'p1', team_id: '1', keys: ['pts'], also: [] } } as never,
        alerts: [], analysis: { boxscore: { p1: { val: 2, adv: {} as never, dev: { pts: 0.9 } } } },
      })),
    })

    it('is a tab of its own, between the match and the lists, and shows the box score of the engine', async () => {
      render(<App initialTab="partido" engine={withBoxscore} loadDemo={loadDemo} />)
      await screen.findByText('EQUIPO PROPIO')
      expect(screen.getAllByRole('tab').map(t => t.textContent)).toEqual(['Partido', 'Boxscore', 'Partidos', 'Acerca de'])
      fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      openTab('Boxscore')
      expect(screen.getByRole('table', { name: /EQUIPO PROPIO/ })).toBeTruthy()
      expect(screen.getByText('A. PROPIA')).toBeTruthy()
      expect(screen.queryByRole('heading', { name: 'Alertas' })).toBeNull()
    })

    it('keeps following the match while it is open: a new action of the player flashes his row', async () => {
      render(<App initialTab="partido" engine={withBoxscore} loadDemo={loadDemo} />)
      await screen.findByText('EQUIPO PROPIO')
      fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      openTab('Boxscore')
      expect(document.querySelector('tr.bx-hit')).toBeNull()
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(document.querySelector('tr.bx-hit')).not.toBeNull()
    })

    it('before the engine has said anything it says there is no match yet', async () => {
      render(<App initialTab="boxscore" engine={fakeEngine()} loadDemo={loadDemo} />)
      await screen.findByText(/sin partido todavía/i)
    })
  })

  it('has no demo notice any more: the matches are chosen in the Partidos tab (issue #476)', async () => {
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    expect(screen.queryByText(/partido de demostración/i)).toBeNull()
    expect(screen.queryByRole('button', { name: /ir a partidos/i })).toBeNull()
  })

  it('has no demo notice once a package is loaded', async () => {
    const store = memoryStore({ plaintext: PKG_TEXT, savedAt: '2026-10-08T12:00:00Z' } as never)
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} store={store} />)
    await screen.findByText('EQUIPO PROPIO')
    expect(screen.queryByText(/partido de demostración/i)).toBeNull()
  })
})
