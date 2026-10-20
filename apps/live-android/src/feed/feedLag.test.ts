import { describe, expect, it } from 'vitest'
import { FeedLagMeter, lagNote, lagText, type LagInfo } from './feedLag'

const T0 = Date.UTC(2026, 9, 17, 19, 0, 0)            // 17-10-2026 19:00:00 UTC
const utc = (secondsAfter: number) => new Date(T0 + secondsAfter * 1000).toISOString().slice(0, 19).replace('T', ' ')
const line = (num: number, loggedAt: number) => ({ num: String(num), logUtc: utc(loggedAt) })
const poll = (at: number, lines: { num: string; logUtc: string | null }[], ageS: number | null = null): LagInfo => ({ receivedAt: T0 + at * 1000, ageS, lines })

describe('FeedLagMeter (issue #411)', () => {
  it('measures, per new line, the time between FEB logging it and the poll that first saw it', () => {
    const meter = new FeedLagMeter()
    meter.observe(poll(100, [line(1, 10), line(2, 20)]))                      // the first poll is the catch-up: not measured
    meter.observe(poll(110, [line(1, 10), line(2, 20), line(3, 70), line(4, 75)]))   // lags 40 and 35
    meter.observe(poll(120, [line(1, 10), line(2, 20), line(3, 70), line(4, 75), line(5, 60)]))   // 60
    const s = meter.summary()!
    expect(s.samples).toBe(3)
    expect(s.medianS).toBe(40)
    expect(s.maxS).toBe(60)
    expect(s.polls).toBe(3)
    expect(s.pollsWithNews).toBe(2)
  })

  it('does not count a line twice, nor the corrections of a line it already has', () => {
    const meter = new FeedLagMeter()
    meter.observe(poll(0, [line(1, -10)]))
    meter.observe(poll(10, [line(1, -10), line(2, 0)]))
    meter.observe(poll(20, [line(1, -10), line(2, 0)]))
    meter.observe(poll(30, [{ num: '2', logUtc: utc(25) }, line(1, -10)]))           // line 2 was corrected
    expect(meter.summary()!.samples).toBe(1)
  })

  it('takes the 90th percentile and the median of the cache age FEB announces', () => {
    const meter = new FeedLagMeter()
    meter.observe(poll(0, [line(0, -5)], 3))
    for (let i = 1; i <= 10; i++) meter.observe(poll(10 * i, Array.from({ length: i + 1 }, (_, n) => line(n, n === i ? 10 * i - 5 * i : -5)), i))
    const s = meter.summary()!
    expect(s.samples).toBe(10)
    expect(s.p90S).toBeGreaterThanOrEqual(s.medianS)
    expect(s.ageMedianS).toBe(5)
  })

  it('ignores lines without a time and says nothing when there is nothing to say', () => {
    const meter = new FeedLagMeter()
    expect(meter.summary()).toBeNull()
    meter.observe(poll(0, [{ num: '1', logUtc: null }]))
    meter.observe(poll(10, [{ num: '1', logUtc: null }, { num: '2', logUtc: null }]))
    expect(meter.summary()!.samples).toBe(0)
  })

  it('knows when the clock of the device is behind FEB (a negative lag is not a measure)', () => {
    const meter = new FeedLagMeter()
    meter.observe(poll(0, [line(1, 0)]))
    for (let i = 1; i <= 6; i++) meter.observe(poll(10 * i, [line(1, 0), line(i + 1, 10 * i + 30)]))     // logged "in the future"
    expect(meter.summary()!.skewed).toBe(true)
    expect(lagText(meter.summary()!)).toMatch(/reloj de la tablet/i)
  })
})

describe('what the staff reads', () => {
  const summary = { samples: 40, medianS: 39.4, p90S: 61, maxS: 67.4, ageMedianS: 11, polls: 100, pollsWithNews: 28, skewed: false }

  it('a line for the connection panel, only with enough samples', () => {
    expect(lagText(summary)).toBe('Datos de FEB con unos 39 s de retraso (el 90 % llega en menos de 61 s).')
    expect(lagText({ ...summary, samples: 3 })).toBeNull()
  })

  it('a note for the session log with the three facts that decide the refresh rate', () => {
    expect(lagNote(summary)).toBe(
      'Retraso de los datos de FEB: mediana 39 s, p90 61 s, máx. 67 s (40 líneas); caché de FEB: 11 s de mediana; 28 % de los sondeos traen novedades')
    expect(lagNote({ ...summary, ageMedianS: null, samples: 0 })).toContain('sin líneas medidas')
  })
})
