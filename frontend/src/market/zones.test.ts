import { beforeEach, describe, expect, it } from 'vitest'
import { loadCompetitionRows, loadCompetitionZones, loadTalentCompetitions, resetTalentData, setTalentBase } from './data'
import { LOW_SAMPLE_ATTEMPTS, RATING_PP, ZONE_KEYS, zoneChart, zoneLines, zoneTotal, type ZoneLine } from './zones'
import { FBCYL_KEY, LF2_KEY, serveTalentData, TALENT_BASE } from '@/test/talentDataHost'

/** The shots by zone of a row (#994) over the REAL file of the exporter: LF2 2025 and FBCYL 2026. */
beforeEach(() => { localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); serveTalentData() })

describe('the zones file of a competition', () => {
  it('is opened with the same key as the rows and has the ten zones of the engine in a fixed order', async () => {
    const zones = await loadCompetitionZones(LF2_KEY)
    expect(zones.zones).toEqual([...ZONE_KEYS])
    expect(zones.league).toHaveLength(20)
    expect(Object.keys(zones.players).length).toBeGreaterThan(0)
  })

  it('says it when the competition has no zones file, instead of failing', async () => {
    const entry = (await loadTalentCompetitions()).find(e => e.key === LF2_KEY)!
    expect(entry.zones).toBeDefined()
    await expect(loadCompetitionZones('feb|no-existe|2025')).rejects.toThrow(/no tiene datos/i)
  })
})

describe('the zones of a row', () => {
  it('has a line per zone with made, attempted and the percentage, and the league percentage to compare with', async () => {
    const zones = await loadCompetitionZones(LF2_KEY)
    const row = (await loadCompetitionRows(LF2_KEY)).rows.find(r => r.person_id === 'feb:10101')!
    const lines = zoneLines(zones, row.person_id, row.team_id)!
    expect(lines.map(l => l.key)).toEqual([...ZONE_KEYS])
    expect(lines.every(l => l.made <= l.att)).toBe(true)
    const withShots = lines.find(l => l.att > 0)!
    expect(withShots.pct).toBeCloseTo((100 * withShots.made) / withShots.att, 5)
    expect(withShots.leaguePct).not.toBeNull()
    expect(lines.find(l => l.att === 0)?.pct ?? null).toBeNull()                         // no shots there: no percentage, never a 0 %
  })

  it('is null for a row without shots, and the total adds up the zones', async () => {
    const zones = await loadCompetitionZones(LF2_KEY)
    expect(zoneLines(zones, 'feb:no-existe', '1')).toBeNull()
    const lines = zoneLines(zones, 'feb:10101', '101')!
    expect(zoneTotal(lines)).toEqual({ made: lines.reduce((a, l) => a + l.made, 0), att: lines.reduce((a, l) => a + l.att, 0) })
  })

  it('works for FBCYL too, keyed by the uuid', async () => {
    const zones = await loadCompetitionZones(FBCYL_KEY)
    const lines = zoneLines(zones, 'fbcyl:34001-00', '34001')!
    expect(zoneTotal(lines).att).toBeGreaterThan(0)
  })
})

const line = (over: Partial<ZoneLine>): ZoneLine => ({ key: 'restricted_area', label: 'Área restringida', points: 2, made: 0, att: 0, pct: null, leaguePct: null, ...over })

describe('the zones as the court of Analytics draws them (#1010)', () => {
  it('rates each zone against the league: above from +8 points, below from -8 and around in between, with the same 8 points as the scouting reports', () => {
    expect(RATING_PP).toBe(8)
    const rate = (pct: number, league: number) => zoneChart([line({ made: pct, att: 100, pct, leaguePct: league })])[0].rating
    expect(rate(58, 50)).toBe('above')                                   // exactly +8
    expect(rate(57.9, 50)).toBe('average')
    expect(rate(42, 50)).toBe('below')                                   // exactly -8
    expect(rate(42.1, 50)).toBe('average')
  })

  it('leaves a zone without shots out, and a zone without a league figure unrated (never invented)', () => {
    const chart = zoneChart([line({ key: 'key_area', att: 0 }), line({ key: 'short_mid_range', made: 5, att: 10, pct: 50, leaguePct: null })])
    expect(chart.map(z => z.zone)).toEqual(['short_mid_range'])
    expect(chart[0].rating).toBe('unknown')
  })

  it('marks few attempts as a small sample, and says made, attempted, percentage, points and name as the court wants them', () => {
    expect(LOW_SAMPLE_ATTEMPTS).toBe(10)
    const [few, enough] = zoneChart([line({ key: 'key_area', label: 'Zona', made: 2, att: 9, pct: (100 * 2) / 9, leaguePct: 40 }), line({ key: 'left_wing_three', label: '45° izquierda', points: 3, made: 4, att: 10, pct: 40, leaguePct: 40 })])
    expect(few.low_sample).toBe(true)
    expect(enough).toMatchObject({ zone: 'left_wing_three', zone_label: '45° izquierda', points: 3, fga: 10, fgm: 4, fg_pct: 40, low_sample: false, rating: 'average', league_pct: 40, delta_pp: 0 })
  })

  it('does not change the lines it is given', () => {
    const lines = [line({ made: 3, att: 6, pct: 50, leaguePct: 40 })]
    const copy = JSON.parse(JSON.stringify(lines))
    zoneChart(lines)
    expect(lines).toEqual(copy)
  })
})
