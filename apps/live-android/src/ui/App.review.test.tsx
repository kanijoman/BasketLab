// Issue #344: with a package loaded there was no way back to the demo match (Zamora-Leon) or to the recorded matches; they were out of the app.
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { FakeFeb, type Pack } from '../feed/fakeFeb'
import { PKG_TEXT, fakeEngine, loadDemo, memoryStore } from './appTestKit'
import { pickOption } from '../test/select'
import { COMPAT_KEY } from '../feed/compatMigration'
import { memoryFinishedStore } from '../feed/finishedStore'

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

const toDemos = () => {
  fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
  pickOption('Tipo de partido', 'demo')
}
/** Reviewing a recorded match is chosen in Partidos (issue #509): the Partido tab has no «Qué partido ver» any more. */
const review = () => {
  toDemos()
  fireEvent.click(screen.getByRole('button', { name: /ver recoletas zamora/i }))
}
const toLive = () => {
  fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
  pickOption('Tipo de partido', 'live')
}
const backToPackage = () => {
  toLive()
  fireEvent.click(screen.getByRole('button', { name: /ver el partido del paquete/i }))
}

describe('review the recorded matches with a package loaded (issues #344, #509)', () => {
  it('a package that is loaded starts in its own match, and there is no «Qué partido ver» in the Partido tab', async () => {
    await open()
    expect(screen.queryByRole('radiogroup', { name: /qué partido ver/i })).toBeNull()
    expect(screen.queryByLabelText(/partido de la demostración/i)).toBeNull()
    expect(screen.getByRole('button', { name: /conectar con feb/i })).toBeTruthy()
  })

  it('without a package the recorded matches are already there', async () => {
    await open({ store: memoryStore(null) })
    expect(screen.getByLabelText(/partido de la demostración/i)).toBeTruthy()
  })

  it('a demo chosen in Partidos opens the recorded match and the package stays saved', async () => {
    const { store, engine } = await open()
    review()
    await waitFor(() => expect(engine.start).toHaveBeenLastCalledWith('REALPKG'))
    expect(await screen.findByLabelText(/partido de la demostración/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /conectar con feb/i })).toBeNull()
    expect(store.saved?.plaintext).toBe(PKG_TEXT)
    toLive()
    expect(screen.getByRole('button', { name: /quitar paquete/i })).toBeTruthy()          // still loaded
  })

  it('the sample game can be reviewed too', async () => {
    await open()
    toDemos()
    expect(screen.getByRole('button', { name: /ver partido de ejemplo/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /ver recoletas zamora/i })).toBeTruthy()
  })

  it('«Ver el partido del paquete» (in Partidos) loads the package again, with the live connection', async () => {
    const { engine } = await open()
    review()
    await screen.findByLabelText(/partido de la demostración/i)
    backToPackage()
    await waitFor(() => expect(engine.start).toHaveBeenLastCalledWith(PKG_TEXT))
    expect(await screen.findByRole('button', { name: /conectar con feb/i })).toBeTruthy()
    expect(screen.queryByLabelText(/partido de la demostración/i)).toBeNull()
  })

  it('while the package match is the one on screen there is no button to go back to it', async () => {
    await open()
    toLive()
    expect(screen.queryByRole('button', { name: /ver el partido del paquete/i })).toBeNull()
  })

  it('removing the package while reviewing leaves just the recorded matches, as before', async () => {
    const { store } = await open()
    review()
    await screen.findByLabelText(/partido de la demostración/i)
    toLive()
    fireEvent.click(screen.getByRole('button', { name: /quitar paquete/i }))
    await waitFor(() => expect(store.saved).toBeNull())
    fireEvent.click(screen.getByRole('tab', { name: 'Partido' }))
    expect(await screen.findByLabelText(/partido de la demostración/i)).toBeTruthy()
  })

  it('cannot be switched away from a live connection that is running (the demos cannot be opened)', async () => {
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
    toDemos()
    expect((screen.getByRole('button', { name: /ver recoletas zamora/i }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/desconecta antes de abrir una demostración/i)).toBeTruthy()
  })
})

// 0.4.1 raises REPLAY_COMPAT: the first start clears what an older version kept and says which, in the Partidos tab (issue #562)
describe('matches kept by an older version', () => {
  const old = (code: string) => ({ code, title: `LEON – ${code}`, savedAt: '2026-10-2' + code + 'T20:00:00Z', ownId: '1', alerts: [], plaintext: '{}', game: '{}' })

  it('are cleared at the first start, which says how many and which', async () => {
    localStorage.removeItem(COMPAT_KEY)
    const finishedStore = memoryFinishedStore([old('1'), old('2')])
    render(<App engine={fakeEngine()} loadDemo={loadDemo} store={memoryStore()} finishedStore={finishedStore} />)
    expect(await screen.findByText(/se han eliminado 2 partidos guardados con una versión anterior/i)).toBeTruthy()
    expect(await finishedStore.list()).toEqual([])
  })

  it('say nothing when there was nothing to clear', async () => {
    localStorage.removeItem(COMPAT_KEY)
    render(<App engine={fakeEngine()} loadDemo={loadDemo} store={memoryStore()} finishedStore={memoryFinishedStore()} />)
    await screen.findByRole('tab', { name: 'Partidos' })
    await waitFor(() => expect(localStorage.getItem(COMPAT_KEY)).not.toBeNull())
    expect(screen.queryByText(/se han eliminado/i)).toBeNull()
  })
})
