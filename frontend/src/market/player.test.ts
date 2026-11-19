import { beforeEach, describe, expect, it } from 'vitest'
import { loadCompetitionRows, loadTalentCompetitions, resetTalentData, setTalentBase, type TalentCompetitionEntry } from './data'
import { bioOf, personRows, radarAxes, RADAR_AXES, trajectory } from './player'
import { toSearchRow, type SearchRow } from './search'
import { FBCYL_KEY, LF2_KEY, serveTalentData, TALENT_BASE } from '@/test/talentDataHost'

/** The profile of a player (B4, #880) over the REAL rows of the exporter: LF2 2025 (with bio) and FBCYL 2026 (without). Other seasons are the same rows moved in time, as a person's career is. */
beforeEach(() => { localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); serveTalentData() })

async function rowsOf(key: string, patch: Partial<TalentCompetitionEntry> = {}): Promise<SearchRow[]> {
  const entry = { ...(await loadTalentCompetitions()).find(e => e.key === key)!, ...patch }
  return (await loadCompetitionRows(key)).rows.map(r => toSearchRow(entry, r))
}

const ANA = 'feb:10100'

describe('the rows of a person', () => {
  it('are only his, from every competition, whatever the order', async () => {
    const lf2 = await rowsOf(LF2_KEY)
    const fbcyl = await rowsOf(FBCYL_KEY)
    const mine = personRows([...fbcyl, ...lf2].reverse(), ANA)
    expect(mine.length).toBeGreaterThan(0)
    expect(mine.every(r => r.person_id === ANA)).toBe(true)
    expect(personRows([...lf2, ...fbcyl], 'feb:no-existe')).toEqual([])
  })
})

describe('the trajectory', () => {
  it('goes from the oldest season to the latest, with the competition and the team of each, and the age of that season', async () => {
    const now = await rowsOf(LF2_KEY)
    const before = await rowsOf(LF2_KEY, { season: '2023', season_label: '2023/2024' })
    const seasons = trajectory(personRows([...now, ...before], ANA))
    expect(seasons.map(s => s.season)).toEqual(['2023', '2025'])
    expect(seasons[0].rows.every(r => r.season === '2023')).toBe(true)
    expect(seasons[0].age).not.toBeNull()
    expect(seasons[1].age! - seasons[0].age!).toBe(2)
  })

  it('has a main row per season: the one with the most minutes, and a tie goes to the first by competition and team (the order of the input does not matter)', async () => {
    const lf2 = personRows(await rowsOf(LF2_KEY), ANA)
    const a = { ...lf2[0], team_id: 'z', team_name: 'Z', minutes: 600 }
    const b = { ...lf2[0], team_id: 'a', team_name: 'A', minutes: 600 }
    const c = { ...lf2[0], team_id: 'm', team_name: 'M', minutes: 100 }
    for (const rows of [[a, b, c], [c, b, a], [b, c, a]]) expect(trajectory(rows)[0].main.team_id).toBe('a')
  })

  it('says when the team or the competition changed since the previous season, and nothing for the first one or for the same team', async () => {
    const base = personRows(await rowsOf(LF2_KEY), ANA)[0]
    const rows: SearchRow[] = [
      { ...base, season: '2022', season_label: '2022/2023' },
      { ...base, season: '2023', season_label: '2023/2024' },
      { ...base, season: '2024', season_label: '2024/2025', team_id: 'otro', team_name: 'Otro' },
      { ...base, season: '2025', season_label: '2025/2026', team_id: 'otro', team_name: 'Otro', comp_key: 'feb|lf1|2025', competition: 'LF Endesa' },
    ]
    expect(trajectory(rows).map(s => s.change)).toEqual([null, null, 'team', 'competition'])
  })

  it('a transfer inside a season keeps both rows in it, and the season has no change of its own', async () => {
    const base = personRows(await rowsOf(LF2_KEY), ANA)[0]
    const season = trajectory([{ ...base, minutes: 900 }, { ...base, team_id: 'otro', team_name: 'Otro', minutes: 300 }])
    expect(season).toHaveLength(1)
    expect(season[0].rows.map(r => r.team_id)).toEqual([base.team_id, 'otro'])
  })

  it('is empty for nobody', () => { expect(trajectory([])).toEqual([]) })
})

describe('the bio', () => {
  it('takes each field from his latest row that says it and says where it came from when the roster of that row did not', async () => {
    const base = personRows(await rowsOf(LF2_KEY), ANA)[0]
    const rows: SearchRow[] = [
      { ...base, season: '2023', height: 170, birth: '2004-05-06', position: 'Base', bio_from: {} },
      { ...base, season: '2025', height: null, birth: '2004-05-06', position: null, bio_from: {} },
      { ...base, season: '2024', height: 172, birth: null, position: 'Escolta', bio_from: { height: '2023:10' } },
    ]
    const bio = bioOf(rows)
    expect(bio.height).toEqual({ value: 172, from: '2023:10' })                     // the latest that has it is 2024, whose own roster said it was another team's
    expect(bio.position).toEqual({ value: 'Escolta', from: null })
    expect(bio.birth).toEqual({ value: '2004-05-06', from: null })
  })

  it('says a field nobody says as no data, never as a zero (FBCYL has no bio)', async () => {
    const bio = bioOf(personRows(await rowsOf(FBCYL_KEY), (await rowsOf(FBCYL_KEY))[0].person_id))
    expect(bio.height).toEqual({ value: null, from: null })
    expect(bio.birth.value).toBeNull()
  })

  it('names the player by his full name when there is one', async () => {
    const base = personRows(await rowsOf(LF2_KEY), ANA)[0]
    expect(bioOf([{ ...base, full_name: 'ANA PRUEBA UNO CASTRO' }]).name).toBe('ANA PRUEBA UNO CASTRO')
    expect(bioOf([{ ...base, full_name: null }]).name).toBe(base.name)
  })
})

describe('the radar', () => {
  it('is the percentiles of the row in its own competition, in a fixed order, with the turnovers named as «less is better»', async () => {
    const row = personRows(await rowsOf(LF2_KEY), ANA)[0]
    const axes = radarAxes(row)
    expect(axes.map(a => a.key)).toEqual(RADAR_AXES.map(a => a.key))
    expect(axes.every(a => a.value === null || (a.value >= 0 && a.value <= 100))).toBe(true)
    expect(axes.find(a => a.key === 'tov')!.label).toMatch(/Cuidar el balón/)
  })

  it('has no values for a row without profile and does not read them as zero', async () => {
    const row = personRows(await rowsOf(LF2_KEY), ANA)[0]
    expect(radarAxes({ ...row, pct: null }).every(a => a.value === null)).toBe(true)
  })
})
