import { beforeEach, describe, expect, it } from 'vitest'
import { DataUnavailable } from '@/datasource/resolve'
import { loadCompetitionRows, loadTalentCompetitions, resetTalentData, setTalentBase, TALENT_DEFAULT_BASE, TalentDataUnavailable } from './data'
import { FBCYL_KEY, LF2_KEY, serveTalentData, TALENT_BASE } from '@/test/talentDataHost'
import type { WebDataHost } from '@/test/webDataHost'

/** BasketLab Talent reads `talent-data` (#878) as the browser would: against the REAL publication of the exporter (`tests/local_vectors/talent_data`), sealed with the open key of the beta. */
let host: WebDataHost
beforeEach(() => { localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); host = serveTalentData() })

describe('the competitions of talent-data', () => {
  it('are the entries of its manifest, one per competition and season, with what the exporter says of each', async () => {
    const competitions = await loadTalentCompetitions()
    expect(competitions.map(c => c.key)).toEqual([FBCYL_KEY, LF2_KEY])
    const lf2 = competitions.find(c => c.key === LF2_KEY)!
    expect(lf2).toMatchObject({ league: 'feb', competition: 'L.F.-2', season: '2025', season_label: '2025/2026', gender: 'F', level: 3 })
    expect(lf2.players).toBeGreaterThan(0)
    expect(competitions.find(c => c.key === FBCYL_KEY)).toMatchObject({ league: 'fbcyl', competition: 'Primera Nacional Femenina', season: '2026' })
  })

  it('are read from index.json once', async () => {
    await loadTalentCompetitions()
    await loadTalentCompetitions()
    expect(host.requested).toEqual(['index.json'])
  })

  it('the default place is the branch of talent-data, never the one of web-data (two publications, two branches)', () => {
    expect(TALENT_DEFAULT_BASE).toBe('https://raw.githubusercontent.com/kanijoman/BasketLab/talent-data/')
  })
})

describe('the rows of a competition', () => {
  it('open with the open key and are what the exporter wrote: totals, the figures in the context of the team, rates, percentiles and bio', async () => {
    const { competition, rows } = await loadCompetitionRows(LF2_KEY)
    expect(competition).toMatchObject({ key: LF2_KEY, competition: 'L.F.-2' })
    expect(rows).toHaveLength((await loadTalentCompetitions()).find(c => c.key === LF2_KEY)!.players)
    const ana = rows.find(r => r.person_id === 'feb:10100')!
    expect([ana.team_id, ana.games, ana.pts, ana.usage_pct, ana.orating, ana.pie]).toEqual(['101', 6, 61, 21.5, 113.5, 7.67])      // the numbers of the Players page vectors
    expect(ana.per40!.pts).toBeGreaterThan(0)
    expect(ana.pct!.pts).toBeGreaterThanOrEqual(0)
    expect(ana.pct!.pts).toBeLessThanOrEqual(100)
    expect(ana).toMatchObject({ birth: '2004-05-06', height: 178, position: 'Base', full_name: 'ANA PRUEBA UNO', eligible: true })
  })

  it('FBCYL rows have their minutes in seconds and no bio', async () => {
    const { rows } = await loadCompetitionRows(FBCYL_KEY)
    const row = rows.find(r => r.person_id === 'fbcyl:34001-00')!
    expect(row.minutes % 60).toBe(0)
    expect(row.minutes).toBeGreaterThan(0)
    expect(row.birth).toBeNull()
  })

  it('a competition that is not published is unavailable, and so is a file that has gone (after reading the manifest again)', async () => {
    await expect(loadCompetitionRows('feb|nope|2025')).rejects.toBeInstanceOf(TalentDataUnavailable)
    await expect(loadCompetitionRows('feb|nope|2025')).rejects.toBeInstanceOf(DataUnavailable)
    const lf2 = (await loadTalentCompetitions()).find(c => c.key === LF2_KEY)!
    host.override[lf2.file] = null
    await expect(loadCompetitionRows(LF2_KEY)).rejects.toThrow(/han cambiado/)
  })
})
