// Live mode of the app (issue #217): a loaded package + "Conectar con FEB" -> the feed client polls FEB and the
// engine is fed with the merged documents; alerts and the connection status show up.
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'
import { FakeFeb, type Pack } from '../feed/fakeFeb'
import type { PackageStore, StoredPackage } from '../package/storage'
import { memoryFinishedStore, type FinishedMatch } from '../feed/finishedStore'
import { decodeRecording, memoryRecordingStore, type SavedRecording } from '../feed/recordingStore'

const META = {
  package_id: 'p', schema_version: 1, created_at: '', collection: 'c', season: '2025',
  team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' },
}

const out = (alerts: EngineOutput['alerts'] = []): EngineOutput => ({
  snapshot: { period: 1, remaining: 593, elapsed: 7, score: { '1': 2, '2': 0 } } as never,
  alerts,
  analysis: {},
})

const ALERT = {
  key: 'foul:9:3', id: 'foul_trouble', severity: 'critical' as const, category: 'faltas',
  message: 'J. PÉREZ: 4 faltas personales. Gestionar sus minutos.', evidence: {}, rearm_s: null, proposal: [],
}

function fakeEngine(over: Partial<EngineApi> = {}): EngineApi {
  return {
    start: vi.fn().mockResolvedValue(META),
    loadReplay: vi.fn().mockResolvedValue({ duration: 100, status: 'FINISHED' }),
    replay: vi.fn(),
    update: vi.fn(async () => out()),
    loadRecording: vi.fn(),
    playRecording: vi.fn(),
    report: vi.fn(),
    beginRecording: vi.fn().mockResolvedValue(undefined),
    recordGap: vi.fn().mockResolvedValue(undefined),
    recording: vi.fn().mockResolvedValue(null),
    setMode: vi.fn().mockResolvedValue(undefined),
    dispose: vi.fn(),
    ...over,
  }
}

const PKG = JSON.stringify({
  checksum: 'x',
  package: {
    team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' }, season: '2025-2026',
    collection: 'c', created_at: '2026-10-08T12:00:00Z', tables: { players: {}, rival_players: {} },
    baselines: { sample_games: { own: 5, rival: 4, league: 50 } },
    competition_meta: { match: { code: '2524475' } },
  },
})
const SAVED: StoredPackage = { plaintext: PKG, savedAt: '2026-10-09T10:00:00Z' }

function memoryStore(): PackageStore {
  let saved: StoredPackage | null = SAVED
  return { load: async () => saved, save: async r => { saved = r }, clear: async () => { saved = null } }
}

const pack: Pack = {
  v: 1, match: '2524475',
  base: { HEADER: { TEAM: [{ id: '1', pts: '0' }, { id: '2', pts: '0' }] }, BOXSCORE: { TEAM: [] }, PLAYBYPLAY: {}, SHOTCHART: {} },
  lines: [{ f: 0, l: { num: '1' } }], shots: [],
  frames: [
    { t: 0, h: { status: '2', statusText: 'EN DIRECTO', quarter: 1, time: '09:50', pts: { '1': 0, '2': 0 } } },
    { t: 10, h: { status: '3', statusText: 'FINALIZADO', quarter: 4, time: 'FINAL', pts: { '1': 2, '2': 0 } } },
  ],
  gaps: {},
}
// a real (tiny) wait: an instantly-resolving sleep would never let the event loop breathe while the feed retries
const tick = () => new Promise<void>(resolve => setTimeout(resolve, 5))
const instant = { intervalMs: 5, waitingIntervalMs: 5, tailPolls: 0, sleep: tick }
const loadDemo = () => Promise.resolve({ package: 'PKG', game: 'GAME' })

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})

describe('live mode with a package', () => {
  it('connects to the match of the package, feeds the engine with the merged FEB documents and shows the alerts', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10 // already over: the first round brings the final document
    const engine = fakeEngine({ update: vi.fn(async () => out([ALERT])) })
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    expect(await screen.findByText(/J\. PÉREZ: 4 faltas/)).toBeTruthy()
    expect(engine.start).toHaveBeenLastCalledWith(PKG) // a fresh engine session for the match
    const doc = JSON.parse((engine.update as ReturnType<typeof vi.fn>).mock.calls[0][0])
    expect(Object.keys(doc)).toEqual(expect.arrayContaining(['HEADER', 'BOXSCORE', 'PLAYBYPLAY', 'SHOTCHART']))
    expect(feb.requests.some(r => r.url.endsWith('/partido/2524475'))).toBe(true)
    await waitFor(() => expect(screen.getByText(/partido finalizado/i)).toBeTruthy())
  })

  it('presents a burst of alerts one by one instead of in a block (issue #375)', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    const burst = ['uno', 'dos', 'tres'].map(k => ({ ...ALERT, key: `burst:${k}`, severity: 'warning' as const, message: `Aviso ${k}` }))
    const engine = fakeEngine({ update: vi.fn(async () => out(burst)) })
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} alertCooldownMs={150} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))

    expect(await screen.findByText('Aviso uno')).toBeTruthy()
    expect(screen.queryByText('Aviso tres')).toBeNull()                // the others wait their turn
    expect(await screen.findByText('Aviso tres', {}, { timeout: 3000 })).toBeTruthy()
    expect(screen.getAllByText('Aviso uno')).toHaveLength(1)           // nothing is shown twice
  })

  it('a critical alert of the burst is not made to wait (issue #375)', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    const burst = [{ ...ALERT, key: 'burst:w', severity: 'warning' as const, message: 'Aviso previo' }, ALERT]
    const engine = fakeEngine({ update: vi.fn(async () => out(burst)) })
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} alertCooldownMs={2000} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))

    expect(await screen.findByText(/J\. PÉREZ: 4 faltas/)).toBeTruthy()   // at once, before the 2 s cooldown
    expect(screen.queryByText('Aviso previo')).toBeNull()
  })

  it('shows the score and the clock coming from the engine', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    const engine = fakeEngine()
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    await waitFor(() => expect(engine.update).toHaveBeenCalled())
    expect(await screen.findByText('Q1 09:53')).toBeTruthy()
  })

  it('keeps waiting before the match and disconnects on demand', async () => {
    const feb = new FakeFeb(pack)
    feb.at = -100 // not started: FEB answers 404
    const slow = { ...instant, sleep: () => new Promise<void>(resolve => setTimeout(resolve, 20)) }
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={slow} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    expect(await screen.findByText(/esperando el inicio del partido/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /desconectar/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /conectar con feb/i })).toBeTruthy())
  })

  it('reports a failure of the engine on a document without stopping the feed', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    const engine = fakeEngine({ update: vi.fn().mockRejectedValue(new Error('boom')) })
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={{ ...instant, tailPolls: 0 }} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    expect(await screen.findByText(/boom/)).toBeTruthy()
  })
})

/** The matches kept on the device are in the Partidos tab (issue #476). */
const inPartidos = async () => {
  fireEvent.click(await screen.findByRole('tab', { name: 'Partidos' }))
  fireEvent.change(screen.getByLabelText('Tipo de partido'), { target: { value: 'finished' } })
}

// #407: a finished live match is kept on the device and can be reviewed afterwards
describe('finished matches (issue #407)', () => {
  const connectAndFinish = async (finishedStore = memoryFinishedStore(), engine = fakeEngine()) => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} finishedStore={finishedStore} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    await waitFor(() => expect(screen.getByText(/^partido finalizado$/i)).toBeTruthy())
    return { finishedStore, engine }
  }

  it('saves the match when the feed ends, with the package and the last document, and offers to review it', async () => {
    const { finishedStore } = await connectAndFinish()
    await waitFor(async () => expect((await finishedStore.list()).map(m => m.code)).toEqual(['2524475']))
    const saved = (await finishedStore.load('2524475')) as FinishedMatch
    expect(saved.plaintext).toBe(PKG)
    expect(saved.title).toBe('EQUIPO PROPIO – EQUIPO RIVAL')
    expect(saved.competition).toBe('c')                    // the competition of the package, for the filters (#497)
    expect(Object.keys(JSON.parse(saved.game))).toEqual(expect.arrayContaining(['HEADER', 'PLAYBYPLAY', 'SHOTCHART']))
    await inPartidos()
    expect(await screen.findByRole('button', { name: /revisar equipo propio – equipo rival/i })).toBeTruthy()
  })

  it('reviewing it replays the saved document with the saved package, and goes to the Partido tab', async () => {
    const engine = fakeEngine()
    const { finishedStore } = await connectAndFinish(memoryFinishedStore(), engine)
    const saved = await waitFor(async () => { const m = await finishedStore.load('2524475'); if (!m) throw new Error('not yet'); return m })
    await inPartidos()
    fireEvent.click(await screen.findByRole('button', { name: /revisar equipo propio – equipo rival/i }))
    await waitFor(() => expect(engine.loadReplay).toHaveBeenCalledWith(saved.game))
    expect(engine.start).toHaveBeenLastCalledWith(saved.plaintext)
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Partido' }).getAttribute('aria-selected')).toBe('true'))
    expect(screen.queryByRole('button', { name: /conectar con feb/i })).toBeNull()      // a match under review never offers to connect (issue #513)
  })

  it('a saved match can be deleted from the device, asking first (issue #512)', async () => {
    const old: FinishedMatch = { code: '9', title: 'LEON – UNIBASKET', savedAt: '2026-10-17T20:30:00Z', ownId: '1', alerts: [], plaintext: PKG, game: '{"PLAYBYPLAY":{"LINES":[]}}' }
    const finishedStore = memoryFinishedStore([old])
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} store={memoryStore()} febHttp={new FakeFeb(pack).get} feedTiming={instant}
      finishedStore={finishedStore} />)
    await inPartidos()
    fireEvent.click(await screen.findByRole('button', { name: /eliminar leon – unibasket/i }))
    expect(await finishedStore.list()).toHaveLength(1)                       // only asked
    fireEvent.click(screen.getByRole('button', { name: /sí, eliminar/i }))
    await waitFor(async () => expect(await finishedStore.list()).toHaveLength(0))
    expect(await screen.findByText(/todavía no hay partidos finalizados/i)).toBeTruthy()
  })

  it('the matches saved in earlier sessions are listed from the start', async () => {
    const old: FinishedMatch = { code: '9', title: 'LEON – UNIBASKET', savedAt: '2026-10-17T20:30:00Z', ownId: '1', alerts: [], plaintext: PKG, game: '{"PLAYBYPLAY":{"LINES":[]}}' }
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} store={memoryStore()} febHttp={new FakeFeb(pack).get} feedTiming={instant}
      finishedStore={memoryFinishedStore([old])} />)
    await inPartidos()
    expect(await screen.findByRole('button', { name: /revisar leon – unibasket/i })).toBeTruthy()
  })

  it('keeps with the match the own team and every alert the engine raised, with the clock it was shown at (#409)', async () => {
    const engine = fakeEngine({ update: vi.fn(async () => out([ALERT])) })
    const { finishedStore } = await connectAndFinish(memoryFinishedStore(), engine)
    const saved = await waitFor(async () => { const m = await finishedStore.load('2524475'); if (!m) throw new Error('not yet'); return m })
    expect(saved.ownId).toBe('1')
    expect(saved.alerts).toHaveLength(1)
    expect(saved.alerts[0]).toMatchObject({ at: 'Q1 09:53', alert: { key: ALERT.key, message: ALERT.message } })
  })

  it('builds the PDF report of a saved match from its document and alerts, and shares it (#409)', async () => {
    const alerts = [{ alert: ALERT, at: 'Q2 03:00' }]
    const old: FinishedMatch = { code: '9', title: 'LEON – UNIBASKET', savedAt: '2026-10-17T20:30:00Z', ownId: '1', alerts, plaintext: PKG, game: '{"PLAYBYPLAY":{"LINES":[]}}' }
    const report = { match: { own: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' } } }
    const engine = fakeEngine({ report: vi.fn().mockResolvedValue(report) })
    const pdf = { render: vi.fn().mockResolvedValue(new Uint8Array([1, 2, 3])), share: vi.fn().mockResolvedValue(undefined) }
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={new FakeFeb(pack).get} feedTiming={instant}
      finishedStore={memoryFinishedStore([old])} pdf={pdf} />)
    await inPartidos()
    fireEvent.click(await screen.findByRole('button', { name: /informe pdf de leon – unibasket/i }))
    await waitFor(() => expect(pdf.share).toHaveBeenCalled())
    expect(engine.report).toHaveBeenCalledWith(old.game, alerts, '1', {})
    expect(pdf.render).toHaveBeenCalledWith(report)
    expect(pdf.share).toHaveBeenCalledWith(new Uint8Array([1, 2, 3]), 'informe-equipo-propio-equipo-rival-9.pdf', expect.stringContaining('EQUIPO PROPIO'))
  })

  it('says so when the report cannot be built', async () => {
    const old: FinishedMatch = { code: '9', title: 'LEON – UNIBASKET', savedAt: '2026-10-17T20:30:00Z', ownId: '1', alerts: [], plaintext: PKG, game: '{}' }
    const engine = fakeEngine({ report: vi.fn().mockRejectedValue(new Error('boom')) })
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={new FakeFeb(pack).get} feedTiming={instant}
      finishedStore={memoryFinishedStore([old])} pdf={{ render: vi.fn(), share: vi.fn() }} />)
    await inPartidos()
    fireEvent.click(await screen.findByRole('button', { name: /informe pdf de leon – unibasket/i }))
    expect(await screen.findByText(/no se pudo generar el informe/i)).toBeTruthy()
  })

  it('a match that did not reach its end is not saved', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 0
    const finishedStore = memoryFinishedStore()
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} finishedStore={finishedStore} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    await screen.findByText(/en directo/i)
    fireEvent.click(screen.getByRole('button', { name: /desconectar/i }))
    expect(await finishedStore.list()).toEqual([])
  })
})

// #417: the package must be the one of the match
describe('package of another match (issue #417)', () => {
  const mismatched = (): EngineOutput => ({
    snapshot: { period: 1, remaining: 593, elapsed: 7, score: { '1': 2, '9': 0 }, teams: { '1': { name: 'EQUIPO PROPIO', fouls_game: 0 }, '9': { name: 'OTRO RIVAL', fouls_game: 0 } } } as never,
    alerts: [], analysis: {},
    package_match: { ok: false, expected: ['1', '2'], found: ['1', '9'] },
  })

  it('warns that the package is not the one of this match, with the teams of both, and shows no alerts', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    const engine = fakeEngine({ update: vi.fn(async () => mismatched()) })
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    const warning = await screen.findByRole('alert', { name: /paquete de otro partido/i })
    expect(warning.textContent).toMatch(/no corresponde a este partido/i)
    expect(warning.textContent).toMatch(/EQUIPO PROPIO – OTRO RIVAL/)          // what FEB serves
    expect(warning.textContent).toMatch(/EQUIPO PROPIO – EQUIPO RIVAL/)        // what the package was prepared for
    expect(screen.queryByText(/J\. PÉREZ/)).toBeNull()
  })

  it('says nothing when the package is the one of the match', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    const engine = fakeEngine({ update: vi.fn(async () => ({ ...out([ALERT]), package_match: { ok: true, expected: ['1', '2'], found: ['1', '2'] } })) })
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    expect(await screen.findByText(/J\. PÉREZ: 4 faltas/)).toBeTruthy()
    expect(screen.queryByRole('alert', { name: /paquete de otro partido/i })).toBeNull()
  })
})

// #416: the app keeps its own recording of the match it follows live, and the staff can share it
describe('recording of the live feed (issue #416)', () => {
  const RECORDING = { v: 1, match: '2524475', started: '2026-10-19T18:30:00.000Z', frames: [{ t: 0 }, { t: 10 }, { t: 20 }], lines: [], shots: [], gaps: {} }

  const connect = async (over: { engine?: EngineApi; recordingStore?: ReturnType<typeof memoryRecordingStore>; feb?: FakeFeb; get?: unknown } = {}) => {
    const feb = over.feb ?? new FakeFeb(pack)
    if (!over.feb) feb.at = 10
    const engine = over.engine ?? fakeEngine({ recording: vi.fn().mockResolvedValue(RECORDING) })
    const recordingStore = over.recordingStore ?? memoryRecordingStore()
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={(over.get as typeof feb.get) ?? feb.get} feedTiming={instant}
      finishedStore={memoryFinishedStore()} recordingStore={recordingStore} shareFile={vi.fn().mockResolvedValue(undefined)} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    return { engine, recordingStore }
  }

  it('starts recording when it connects and gives every document its time since the first poll', async () => {
    const { engine } = await connect()
    await waitFor(() => expect(engine.update).toHaveBeenCalled())
    expect(engine.beginRecording).toHaveBeenCalledWith('2524475', expect.stringMatching(/^\d{4}-\d{2}-\d{2}T/))
    const [json, at] = (engine.update as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(typeof json).toBe('string')
    expect(at).toBeGreaterThanOrEqual(0)
  })

  it('keeps the recording, complete, when the match ends', async () => {
    const { recordingStore } = await connect()
    const saved = await waitFor(async () => { const r = await recordingStore.load('2524475'); if (!r) throw new Error('not yet'); return r })
    expect(saved).toMatchObject({ complete: true, frames: 3, title: 'EQUIPO PROPIO – EQUIPO RIVAL' })
    expect(JSON.parse(await decodeRecording(saved))).toEqual(RECORDING)
  })

  it('keeps what was recorded, marked incomplete, when the staff disconnects halfway', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 0
    const { recordingStore } = await connect({ feb })
    await screen.findByText(/en directo/i)
    fireEvent.click(screen.getByRole('button', { name: /desconectar/i }))
    const saved = await waitFor(async () => { const r = await recordingStore.load('2524475'); if (!r) throw new Error('not yet'); return r })
    expect(saved.complete).toBe(false)
  })

  it('keeps nothing when no document was recorded', async () => {
    const engine = fakeEngine({ recording: vi.fn().mockResolvedValue(null) })
    const feb = new FakeFeb(pack)
    feb.at = 0
    const { recordingStore } = await connect({ engine, feb })
    await screen.findByText(/en directo/i)
    fireEvent.click(screen.getByRole('button', { name: /desconectar/i }))
    await waitFor(() => expect(engine.recording).toHaveBeenCalled())
    expect(await recordingStore.list()).toEqual([])
  })

  it('tells the recording when FEB fails in the middle of the match', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 0                                  // the match is on: the feed keeps polling
    let shots = 0
    const get = ((url: string, headers?: Record<string, string>) =>
      url.includes('/ShotChart/') && ++shots === 2 ? Promise.resolve({ status: 404, json: null, text: '' }) : feb.get(url, headers))
    const { engine } = await connect({ feb, get })
    await waitFor(() => expect(engine.recordGap).toHaveBeenCalledWith('shotchart', expect.any(Number)))
  })

  it('lists the recordings and shares the file as it is, with a name that says the match', async () => {
    const bytes = new Uint8Array([0x1f, 0x8b, 8, 0])
    const old: SavedRecording = { code: '9', title: 'LEON – UNIBASKET', savedAt: '2026-10-17T20:30:00Z', complete: false, frames: 120, encoding: 'gzip', bytes }
    const shareFile = vi.fn().mockResolvedValue(undefined)
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} store={memoryStore()} febHttp={new FakeFeb(pack).get} feedTiming={instant}
      recordingStore={memoryRecordingStore([old])} shareFile={shareFile} />)
    await inPartidos()
    expect(await screen.findByText(/incompleta/i)).toBeTruthy()
    fireEvent.click(await screen.findByRole('button', { name: /compartir grabación de leon – unibasket/i }))
    await waitFor(() => expect(shareFile).toHaveBeenCalled())
    expect(shareFile).toHaveBeenCalledWith(bytes, 'grabacion-9.rec.json.gz', expect.stringContaining('LEON – UNIBASKET'), 'application/gzip')
  })
})

// #411: how late FEB's data is, measured on the connection
describe('delay of the feed (issue #411)', () => {
  const T0 = Date.UTC(2026, 9, 17, 19, 0, 0)
  const logAt = (ms: number) => new Date(ms).toISOString().slice(0, 19).replace('T', ' ')

  /** A FEB that gets one new line per poll, each logged 40 s before the poll that sees it, with a cache age of 11 s, and then goes quiet. */
  function laggingFeb() {
    let poll = -1
    const lines = () => Array.from({ length: Math.min(poll, 9) + 1 }, (_, n) => ({ num: String(n + 1), LogTimeUtc: logAt(T0 + n * 10_000 - 40_000) }))
    const json = (url: string) => {
      if (url.includes('/BoxScore/')) { poll += 1; return { HEADER: { status: '2', TEAM: [{ id: '1', pts: '0' }, { id: '2', pts: '0' }] }, BOXSCORE: { TEAM: [] } } }
      if (url.includes('/KeyFacts/')) return { PLAYBYPLAY: { LINES: lines() } }
      return { SHOTCHART: { SHOTS: [] } }
    }
    const http = async (url: string) => (url.includes('/partido/')
      ? { status: 200, text: '<input type="hidden" value="eyJhbGciFAKE.one.token">' }
      : { status: 200, text: JSON.stringify(json(url)), headers: { Age: '11' } })
    return { http, polls: () => poll }
  }

  const connected = async () => {
    const feb = laggingFeb()
    // the device clock: 10 s more per poll; the line of each poll was logged 40 s before it
    const now = () => T0 + Math.max(0, feb.polls()) * 10_000
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.http} feedTiming={{ ...instant, now }} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    return feb
  }

  it('shows how late the data is once it has enough lines to say', async () => {
    await connected()
    expect(await screen.findByText(/Datos de FEB con unos 40 s de retraso/, {}, { timeout: 4000 })).toBeTruthy()
  })

  it('writes the delay, the cache age and the share of useful polls in the session log when the connection ends', async () => {
    await connected()
    await screen.findByText(/Datos de FEB con unos 40 s de retraso/, {}, { timeout: 4000 })
    fireEvent.click(screen.getByRole('button', { name: /desconectar/i }))
    fireEvent.click(screen.getByRole('tab', { name: 'Acerca de' }))
    expect(await screen.findByText(/Retraso de los datos de FEB: mediana 40 s, p90 40 s, máx. 40 s \(\d+ líneas\); caché de FEB: 11 s de mediana; \d+ % de los sondeos traen novedades/)).toBeTruthy()
  })
})
