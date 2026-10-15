import { vi } from 'vitest'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'
import type { PackageStore, StoredPackage } from '../package/storage'

/** Shared fakes of the App tests: an engine that answers instantly, an in-memory package store and a tiny demo. */
export const META = {
  package_id: 'p', schema_version: 1, created_at: '', collection: 'c', season: '2025',
  team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' },
}

export const out = (elapsed: number, alerts: EngineOutput['alerts'] = []): EngineOutput => ({
  snapshot: { period: 1, remaining: 600 - elapsed, elapsed, score: { '1': elapsed, '2': elapsed - 1 } } as never,
  alerts,
  analysis: {},
})

export const ALERT = {
  key: 'foul:9:3', id: 'foul_trouble', severity: 'critical' as const, category: 'faltas',
  message: 'J. PÉREZ: 4 faltas personales. Gestionar sus minutos.', evidence: {}, rearm_s: null,
  proposal: [{ type: 'sub', out_id: '9', out_name: 'J. PÉREZ', in_id: '10', in_name: 'L. GÓMEZ' }],
}

export function fakeEngine(over: Partial<EngineApi> = {}): EngineApi {
  return {
    start: vi.fn().mockResolvedValue(META),
    loadReplay: vi.fn().mockResolvedValue({ duration: 100, status: 'FINISHED' }),
    replay: vi.fn(async (e: number) => out(e, e >= 5 ? [ALERT] : [])),
    update: vi.fn(),
    loadRecording: vi.fn().mockResolvedValue({ duration: 100, status: 'GRABACION', match: '2524470', frames: 10 }),
    // seconds 0-2: the match is not there yet; 3-5: FEB answers 404; afterwards the engine output (with an alert)
    playRecording: vi.fn(async (s: number) =>
      s < 3 ? { feed: 'waiting' as const, output: null }
        : s < 6 ? { feed: 'gap' as const, output: null }
          : { feed: 'ok' as const, output: out(s, s >= 8 ? [ALERT] : []) }),
    setMode: vi.fn().mockResolvedValue(undefined),
    dispose: vi.fn(),
    ...over,
  }
}


export const PKG_TEXT = JSON.stringify({
  checksum: 'x',
  package: {
    team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' }, season: '2025-2026',
    collection: 'c', created_at: '2026-10-08T12:00:00Z',
    tables: { players: { a: {} }, rival_players: { b: {} } }, baselines: { sample_games: { own: 5, rival: 4, league: 50 } },
  },
})

export function memoryStore(initial: StoredPackage | null = null): PackageStore & { saved: StoredPackage | null } {
  const s = {
    saved: initial,
    load: async () => s.saved,
    save: async (r: StoredPackage) => { s.saved = r },
    clear: async () => { s.saved = null },
  }
  return s
}

export const loadDemo = () => Promise.resolve({ package: 'PKG', game: 'GAME' })
export const replayCalls = (e: EngineApi) => (e.replay as ReturnType<typeof vi.fn>).mock.calls

