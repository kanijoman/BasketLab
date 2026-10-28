/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { NAV_GROUPS, NAV_ITEMS } from './nav'

// Issue #191 (U4): ONE definition of the navigation of a collection, for the sidebar, the menu of the phone and the cards of the hub.
describe('navigation of a collection (issue #191)', () => {
  const app = readFileSync(join(__dirname, '..', 'App.tsx'), 'utf8')
  const routes = [...app.matchAll(/<Route path="([a-z-]+)"\s+element/g)].map(m => m[1]).filter(p => p !== 'collection')

  it('groups the pages by what the staff does with them', () => {
    expect(NAV_GROUPS.map(g => g.label)).toEqual(['Equipos', 'Jugadores', 'Partido', 'Live', 'Informes'])
  })

  it('has an entry for every page of a collection and none for a page that does not exist', () => {
    const paths = NAV_ITEMS.map(i => i.subPath)
    expect(paths.filter(p => p !== '').sort()).toEqual([...routes].sort())
    expect(new Set(paths).size).toBe(paths.length)                      // a page is in ONE group
  })

  it('every entry says what it is for (the card of the hub)', () => {
    for (const item of NAV_ITEMS) expect(item.description.length, item.subPath || 'resumen').toBeGreaterThan(10)
  })
})
