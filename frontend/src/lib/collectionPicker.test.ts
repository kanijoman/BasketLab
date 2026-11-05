import { describe, expect, it } from 'vitest'
import type { CollectionInfo } from '@/api/client'
import { pickCollection, selectionOf } from './collectionPicker'

// Issue #761: the competition is chosen by ámbito → temporada → competición → grupo, each level filtered by the previous ones.
const c = (name: string, league: string, competition: string, season: string, group = ''): CollectionInfo =>
  ({ name, league, competition, season, group, game_count: 10 }) as CollectionInfo

const LIST = [
  c('FEB_LF2_25_A', 'FEB', 'LF2', '2025-2026', 'A'),
  c('FEB_LF2_25_B', 'FEB', 'LF2', '2025-2026', 'B'),
  c('FEB_LF2_24_A', 'FEB', 'LF2', '2024-2025', 'A'),
  c('FEB_LF1_25', 'FEB', 'LF1', '2025-2026'),
  c('FBCYL_U16_25', 'FBCYL', 'U16', '2025-2026'),
  c('AND_SEN_25', 'ANDALUCIA', 'Senior', '2025-2026'),
]

describe('pickCollection (issue #761)', () => {
  it('lists the ámbitos of the data: FEB and FBCYL first, the others (new federations) after, in order', () => {
    expect(pickCollection(LIST, {}).ambitos).toEqual(['FEB', 'FBCYL', 'ANDALUCIA'])
    expect(pickCollection([c('z', 'MADRID', 'S', '2025'), c('a', 'ARAGON', 'S', '2025'), c('f', 'FBCYL', 'S', '2025')], {}).ambitos).toEqual(['FBCYL', 'ARAGON', 'MADRID'])
  })

  it('with nothing chosen it preselects the latest season, the first competition and the first group', () => {
    const p = pickCollection(LIST, {})
    expect(p.selection).toEqual({ ambito: 'FEB', season: '2025-2026', competition: 'LF1', group: '' })
    expect(p.seasons).toEqual(['2025-2026', '2024-2025'])
    expect(p.collection?.name).toBe('FEB_LF1_25')
  })

  it('each level only offers what the previous ones allow', () => {
    const p = pickCollection(LIST, { ambito: 'FEB', season: '2024-2025' })
    expect(p.competitions).toEqual(['LF2'])
    expect(p.groups).toEqual(['A'])
    expect(pickCollection(LIST, { ambito: 'FBCYL' }).competitions).toEqual(['U16'])
  })

  it('a choice that does not exist at the new level falls back to the default instead of leaving an impossible combination', () => {
    // LF1 exists only in 2025-2026: moving to 2024-2025 cannot keep it
    expect(pickCollection(LIST, { ambito: 'FEB', season: '2024-2025', competition: 'LF1' }).selection.competition).toBe('LF2')
    // the ámbito changes: the season of the old one is not offered by the new one
    expect(pickCollection(LIST, { ambito: 'ANDALUCIA', season: '2024-2025' }).collection?.name).toBe('AND_SEN_25')
  })

  it('keeps the competition and the group when they still exist after changing the season', () => {
    const p = pickCollection(LIST, { ambito: 'FEB', season: '2024-2025', competition: 'LF2', group: 'A' })
    expect(p.collection?.name).toBe('FEB_LF2_24_A')
    expect(pickCollection(LIST, { ambito: 'FEB', season: '2025-2026', competition: 'LF2', group: 'B' }).collection?.name).toBe('FEB_LF2_25_B')
  })

  it('a competition without groups has a single empty group (nothing to show)', () => {
    expect(pickCollection(LIST, { competition: 'LF1' }).groups).toEqual([''])
  })

  it('an empty list gives no options and no collection', () => {
    expect(pickCollection([], {})).toMatchObject({ ambitos: [], seasons: [], competitions: [], groups: [], collection: null })
  })

  it('selectionOf gives the levels of a collection, so the header starts on the current one', () => {
    expect(selectionOf(LIST[1])).toEqual({ ambito: 'FEB', season: '2025-2026', competition: 'LF2', group: 'B' })
    expect(pickCollection(LIST, selectionOf(LIST[1])).collection?.name).toBe('FEB_LF2_25_B')
  })
})
