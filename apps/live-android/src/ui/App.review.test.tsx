// Issue #344: with a package loaded there was no way back to the demo match (Zamora-Leon) or to the recorded matches; they were out of the app.
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { FakeFeb, type Pack } from '../feed/fakeFeb'
import { PKG_TEXT, fakeEngine, loadDemo, memoryStore } from './appTestKit'

const MANIFEST = [{
  code: '2524470', title: 'Recoletas Zamora – Mipelletymas B.F. Leon', date: '2026-10-10T17:00',
  home: { id: '2', name: 'EQUIPO RIVAL' }, away: { id: '1', name: 'EQUIPO PROPIO' },
  recording: '2524470.recording.json', package: '2524470.package.json',
}]
const loadManifest = () => Promise.resolve(MANIFEST)
const loadMatch = () => Promise.resolve({ package: 'REALPKG', recording: 'REC' })
const saved = () => ({ plaintext: PKG_TEXT, savedAt: '2026-10-09T10:00:00Z' })

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})

async function open(over: { store?: ReturnType<typeof memoryStore>; engine?: ReturnType<typeof fakeEngine> } = {}) {
  const store = over.store ?? memoryStore(saved())
  const engine = over.engine ?? fakeEngine()
  render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} loadManifest={loadManifest} loadMatch={loadMatch} store={store} />)
  await screen.findByText('EQUIPO PROPIO')
  return { store, engine }
}

const review = () => fireEvent.click(screen.getByRole('radio', { name: /revisar partidos grabados/i }))
const backToPackage = () => fireEvent.click(screen.getByRole('radio', { name: /partido del paquete/i }))

describe('review the recorded matches with a package loaded (issue #344)', () => {
  it('a package that is loaded starts in its own match, and the switch is there', async () => {
    await open()
    expect((screen.getByRole('radio', { name: /partido del paquete/i }) as HTMLInputElement).checked).toBe(true)
    expect((screen.getByRole('radio', { name: /revisar partidos grabados/i }) as HTMLInputElement).checked).toBe(false)
    expect(screen.queryByLabelText(/partido de la demostración/i)).toBeNull()
  })

  it('without a package there is no switch: the recorded matches are already there', async () => {
    await open({ store: memoryStore(null) })
    expect(screen.queryByRole('radio', { name: /revisar partidos grabados/i })).toBeNull()
    expect(screen.getByLabelText(/partido de la demostración/i)).toBeTruthy()
  })

  it('«Revisar» opens the recorded match and the selector, and the package stays saved', async () => {
    const { store, engine } = await open()
    review()
    await waitFor(() => expect(engine.start).toHaveBeenLastCalledWith('REALPKG'))
    expect(await screen.findByLabelText(/partido de la demostración/i)).toBeTruthy()
    expect(screen.getByText(/tu paquete sigue guardado/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /conectar con feb/i })).toBeNull()
    expect(store.saved?.plaintext).toBe(PKG_TEXT)
    fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
    expect(screen.getByRole('button', { name: /quitar paquete/i })).toBeTruthy()          // still loaded
  })

  it('the sample game can be reviewed too', async () => {
    await open()
    review()
    await screen.findByLabelText(/partido de la demostración/i)
    fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
    expect(screen.getByRole('button', { name: /ver partido de ejemplo/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /ver recoletas zamora/i })).toBeTruthy()
  })

  it('«Partido del paquete» loads the package again, with the live connection', async () => {
    const { engine } = await open()
    review()
    await screen.findByLabelText(/partido de la demostración/i)
    backToPackage()
    await waitFor(() => expect(engine.start).toHaveBeenLastCalledWith(PKG_TEXT))
    expect(await screen.findByRole('button', { name: /conectar con feb/i })).toBeTruthy()
    expect(screen.queryByLabelText(/partido de la demostración/i)).toBeNull()
  })

  it('removing the package while reviewing leaves just the recorded matches, as before', async () => {
    const { store } = await open()
    review()
    await screen.findByLabelText(/partido de la demostración/i)
    fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
    fireEvent.click(screen.getByRole('button', { name: /quitar paquete/i }))
    await waitFor(() => expect(store.saved).toBeNull())
    fireEvent.click(screen.getByRole('tab', { name: 'Partido' }))
    expect(await screen.findByLabelText(/partido de la demostración/i)).toBeTruthy()
    expect(screen.queryByRole('radio', { name: /revisar partidos grabados/i })).toBeNull()
  })

  it('cannot be switched away from a live connection that is running', async () => {
    const pack: Pack = {
      v: 1, match: '2524475',
      base: { HEADER: { TEAM: [{ id: '1', pts: '0' }, { id: '2', pts: '0' }] }, BOXSCORE: { TEAM: [] }, PLAYBYPLAY: {}, SHOTCHART: {} },
      lines: [{ f: 0, l: { num: '1' } }], shots: [],
      frames: [{ t: 0, h: { status: '2', statusText: 'EN DIRECTO', quarter: 1, time: '09:50', pts: { '1': 0, '2': 0 } } }], gaps: {},
    }
    const feb = new FakeFeb(pack)
    feb.at = 0
    const engine = fakeEngine({ update: vi.fn(async () => ({ snapshot: { period: 1, remaining: 593, elapsed: 7, score: { '1': 2, '2': 0 } } as never, alerts: [], analysis: {} })) })
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} loadManifest={loadManifest} loadMatch={loadMatch} store={memoryStore({
      plaintext: JSON.stringify({ checksum: 'x', package: { ...JSON.parse(PKG_TEXT).package, competition_meta: { match: { code: '2524475' } } } }),
      savedAt: '2026-10-09T10:00:00Z' })} febHttp={feb.get}
      feedTiming={{ intervalMs: 5, waitingIntervalMs: 5, tailPolls: 0, sleep: () => new Promise<void>(r => setTimeout(r, 20)) }} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    await screen.findByRole('button', { name: /desconectar/i })
    expect((screen.getByRole('radio', { name: /revisar partidos grabados/i }) as HTMLInputElement).disabled).toBe(true)
    expect(screen.getByText(/desconecta antes de revisar/i)).toBeTruthy()
  })
})
