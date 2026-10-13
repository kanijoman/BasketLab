import { describe, expect, it } from 'vitest'
import { FeedbackStore, feedbackFileName, type StorageLike } from './store'
import type { Alert } from '../engine/types'

const alert = (key: string, over: Partial<Alert> = {}): Alert => ({
  key, id: 'fatigue_high', severity: 'warning', category: 'rotacion', message: key, evidence: {}, proposal: [], rearm_s: null, ...over,
})

function memory(): StorageLike & { data: Map<string, string> } {
  const data = new Map<string, string>()
  return {
    data,
    getItem: k => data.get(k) ?? null,
    setItem: (k, v) => { data.set(k, v) },
    removeItem: k => { data.delete(k) },
  }
}

const T0 = '2026-10-17T18:31:00.000Z'
const T1 = '2026-10-17T18:31:20.000Z'

describe('FeedbackStore (issue #235)', () => {
  it('registers an alert when it is shown, without a verdict yet', () => {
    const store = new FeedbackStore('live:2524470', 'pk1', memory())
    store.register(alert('fatigue:1'), 912, T0)
    expect(store.records()).toEqual([{
      key: 'fatigue:1', id: 'fatigue_high', severity: 'warning', category: 'rotacion',
      elapsed: 912, shown_at: T0, verdict: null, decided_at: null,
    }])
  })

  it('registering again keeps the first record: a restart of the live mode does not rewrite the history', () => {
    const store = new FeedbackStore('live:1', null, memory())
    store.register(alert('a'), 100, T0)
    store.setVerdict('a', 'seguida', T1)
    store.register(alert('a'), 100, '2026-10-17T19:00:00.000Z')
    expect(store.records()).toHaveLength(1)
    expect(store.get('a')).toMatchObject({ shown_at: T0, verdict: 'seguida', decided_at: T1 })
  })

  it('stores the verdict with the moment it was decided, and pressing the same one again clears it', () => {
    const store = new FeedbackStore('live:1', null, memory())
    store.register(alert('a'), 100, T0)
    store.setVerdict('a', 'descartada', T1)
    expect(store.get('a')).toMatchObject({ verdict: 'descartada', decided_at: T1 })
    store.setVerdict('a', null, T1)
    expect(store.get('a')).toMatchObject({ verdict: null, decided_at: null })
  })

  it('ignores a verdict for an alert it never saw', () => {
    const store = new FeedbackStore('live:1', null, memory())
    store.setVerdict('ghost', 'seguida', T1)
    expect(store.records()).toEqual([])
  })

  it('persists on the device and a new store of the same match reads it back', () => {
    const storage = memory()
    const first = new FeedbackStore('live:2524470', 'pk1', storage)
    first.register(alert('a'), 100, T0)
    first.setVerdict('a', 'ya_hecho', T1)
    const again = new FeedbackStore('live:2524470', 'pk1', storage)
    expect(again.get('a')).toMatchObject({ verdict: 'ya_hecho', decided_at: T1 })
  })

  it('keeps each match apart', () => {
    const storage = memory()
    new FeedbackStore('live:1', null, storage).register(alert('a'), 100, T0)
    expect(new FeedbackStore('live:2', null, storage).records()).toEqual([])
  })

  it('keeps the order in which the alerts were shown', () => {
    const store = new FeedbackStore('live:1', null, memory())
    ;['c', 'a', 'b'].forEach((k, i) => store.register(alert(k), i, T0))
    expect(store.records().map(r => r.key)).toEqual(['c', 'a', 'b'])
  })

  it('works without storage and survives corrupt or failing storage', () => {
    const noStorage = new FeedbackStore('live:1', null, null)
    noStorage.register(alert('a'), 1, T0)
    noStorage.setVerdict('a', 'seguida', T1)
    expect(noStorage.get('a')?.verdict).toBe('seguida')

    const corrupt = memory()
    corrupt.setItem('basketlab-live-feedback:live:1', '{not json')
    expect(new FeedbackStore('live:1', null, corrupt).records()).toEqual([])

    const broken: StorageLike = {
      getItem: () => { throw new Error('denied') }, setItem: () => { throw new Error('quota') }, removeItem: () => { throw new Error('denied') },
    }
    const store = new FeedbackStore('live:1', null, broken)
    store.register(alert('a'), 1, T0)
    expect(store.records()).toHaveLength(1)
  })

  it('clears the history of the match', () => {
    const storage = memory()
    const store = new FeedbackStore('live:1', null, storage)
    store.register(alert('a'), 1, T0)
    store.clear()
    expect(store.records()).toEqual([])
    expect(new FeedbackStore('live:1', null, storage).records()).toEqual([])
  })

  it('exports a self-describing JSON the evaluator can join by match code and key', () => {
    const store = new FeedbackStore('live:2524470', 'pk1', memory())
    store.register(alert('a'), 100, T0)
    store.setVerdict('a', 'seguida', T1)
    const out = store.export('2026-10-17T21:00:00.000Z')
    expect(out).toEqual({
      v: 1, kind: 'basketlab-live-feedback', exported_at: '2026-10-17T21:00:00.000Z',
      context: 'live:2524470', package_id: 'pk1', entries: store.records(),
    })
    expect(JSON.parse(JSON.stringify(out))).toEqual(out)
  })

  it('names the downloaded file after the match', () => {
    expect(feedbackFileName('live:2524470', '2026-10-17T21:00:00.000Z')).toBe('feedback-live-2524470-2026-10-17.json')
  })
})
