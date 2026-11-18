import { describe, expect, it } from 'vitest'
import { freshnessNotice, STALE_AFTER_HOURS } from './sourceFreshness'
import type { SourceFreshness } from '@/webdata/client'

// The notice of a stale external source (#884, PR C): discreet, with the date of the data, and only when there is something to say: the last run of the source failed, or its last good data is more than a day and
// a half old. A source that is fine says nothing; a competition of FEB or FBCYL never has one; a source the publication does not mention is not a reason to alarm anybody.
const NOW = Date.parse('2026-11-18T12:00:00Z')
const entry = (over: Partial<SourceFreshness>): SourceFreshness => ({ source: 'ncaa', state: 'ok', ok: true, last_ok: '2026-11-18T07:00:00Z', finished: '2026-11-18T07:00:00Z', games: 13, unreliable: 0, published: 13, ...over })
const NCAA = 'NCAA_D1_2026_SEC'

describe('the notice of a source that is not fresh', () => {
  it('says nothing when the last run worked and is recent', () => {
    expect(freshnessNotice(NCAA, [entry({})], NOW)).toBeNull()
  })

  it('says the data is from the day it last worked when the last run failed', () => {
    expect(freshnessNotice(NCAA, [entry({ state: 'failed', ok: false, last_ok: '2026-11-17T07:00:00Z', finished: '2026-11-18T07:00:00Z' })], NOW)).toBe('Datos de NCAA del 17/11: la última actualización falló.')
  })

  it('says it too when the source never worked', () => {
    expect(freshnessNotice(NCAA, [entry({ state: 'failed', ok: false, last_ok: undefined })], NOW)).toBe('La última actualización de NCAA falló.')
  })

  it('says the date when the last good data is old even if nothing failed (the schedule did not run)', () => {
    expect(freshnessNotice(NCAA, [entry({ last_ok: '2026-11-15T07:00:00Z' })], NOW)).toBe('Datos de NCAA del 15/11.')
  })

  it('has a limit of a day and a half: below it nothing, above it the date', () => {
    const hoursAgo = (h: number) => new Date(NOW - h * 3600_000).toISOString().replace(/\.\d+Z$/, 'Z')
    expect(STALE_AFTER_HOURS).toBe(36)
    expect(freshnessNotice(NCAA, [entry({ last_ok: hoursAgo(35.9) })], NOW)).toBeNull()
    expect(freshnessNotice(NCAA, [entry({ last_ok: hoursAgo(36.1) })], NOW)).toMatch(/^Datos de NCAA del \d\d\/\d\d\.$/)
  })

  it.each(['L_F_-2_2025_2026_Liga_Regular_B', 'FBCYL_1ª_FASE-GRUPO_A-1_2026_', 'NCAAB_2026', ''])('never has one for %s (not an external competition)', collection => {
    expect(freshnessNotice(collection, [entry({ state: 'failed', ok: false })], NOW)).toBeNull()
  })

  it('looks at the source of the competition and not at the others', () => {
    const list = [entry({ source: 'fiba', state: 'failed', ok: false }), entry({ source: 'ncaa' })]
    expect(freshnessNotice(NCAA, list, NOW)).toBeNull()
    expect(freshnessNotice('FIBA_U18_EuroBasket_2026_', list, NOW)).toMatch(/FIBA/)
  })

  it('says nothing about a source the publication does not mention, or with no list at all', () => {
    expect(freshnessNotice(NCAA, [entry({ source: 'acb', state: 'failed', ok: false })], NOW)).toBeNull()
    expect(freshnessNotice(NCAA, [], NOW)).toBeNull()
  })

  it('writes the day by its UTC date, so the text does not depend on the time zone of the browser', () => {
    expect(freshnessNotice(NCAA, [entry({ state: 'failed', ok: false, last_ok: '2026-11-17T23:30:00Z' })], NOW)).toContain('17/11')
  })
})
