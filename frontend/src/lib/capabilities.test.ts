import { describe, expect, it } from 'vitest'
import { NAV_ITEMS, type Section } from './nav'
import { isOffered } from './useVisibleNav'

// Issues #1099 and #1100: what each source can do in Analytics. The sections are the ones the publications had for each source on 26/11/2026 (`web-data` for FEB and FBCYL, `web-data-ext` for the
// external ones; measured from their manifests): a page is offered where its section exists and hidden where the origin of the data does not bring it. This is the matrix of docs/ARCHITECTURE.md.
const BASE: Section[] = ['rows', 'matches', 'possessions', 'lineups', 'inout', 'rotations', 'reports']
const SECTIONS: Record<string, Section[]> = {
  FEB: [...BASE, 'derived', 'shots', 'assist_connections', 'calendar'],
  FBCYL: [...BASE, 'derived', 'shots', 'assist_connections', 'calendar'],
  NCAA: [...BASE, 'shots'],                                      // no derived (the PBP analysis), no assist connections, no calendar
  FIBA: [...BASE],                                               // and no coordinates of the shots
}

const offered = (source: string) => NAV_ITEMS.filter(i => i.subPath !== '' && isOffered(i.requires, new Set(SECTIONS[source]))).map(i => i.subPath)
const hidden = (source: string) => NAV_ITEMS.filter(i => i.subPath !== '' && !offered(source).includes(i.subPath)).map(i => i.subPath).sort()


describe('what each source offers in Analytics (#1099, #1100)', () => {
  it('every page of a competition says what it needs from the publication', () => {
    const pages = NAV_ITEMS.filter(i => i.subPath !== '')
    expect(pages.filter(i => !i.requires).map(i => i.subPath)).toEqual([])
    expect(new Set(pages.map(i => i.requires!.section))).toEqual(new Set(['rows', 'derived', 'shots', 'rotations', 'matches', 'possessions', 'lineups', 'inout', 'assist_connections', 'calendar', 'reports']))
  })

  it('FEB and FBCYL, with all their sections, offer every page', () => {
    expect(hidden('FEB')).toEqual([])
    expect(hidden('FBCYL')).toEqual([])
  })

  it('NCAA hides the pages whose data its origin does not bring: PBP analysis, assist connections and, without a calendar, the preview and the simulation', () => {
    expect(hidden('NCAA')).toEqual(['conexiones', 'pbp', 'previa', 'simulacion'])
  })

  it('FIBA hides what NCAA does and the shot chart too: it has no coordinates', () => {
    expect(hidden('FIBA')).toEqual(['conexiones', 'pbp', 'previa', 'shots', 'simulacion'])
  })

  it('a competition with nothing published offers no page, and the summary is never hidden', () => {
    expect(NAV_ITEMS.filter(i => i.subPath !== '' && isOffered(i.requires, new Set())).map(i => i.subPath)).toEqual([])
    expect(NAV_ITEMS.find(i => i.subPath === '')!.requires).toBeUndefined()
  })
})
