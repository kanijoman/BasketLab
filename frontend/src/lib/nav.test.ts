/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { NAV_GROUPS, NAV_ITEMS } from './nav'

// Issue #191 (U4): ONE definition of the navigation of a collection, for the sidebar, the menu of the phone and the cards of the hub.
describe('navigation of a collection (issue #191)', () => {
  const app = readFileSync(join(__dirname, '..', 'App.tsx'), 'utf8')
  // Pages taken out of the web (their code is kept): they redirect to the hub, so they are routes without an entry.
  const RETIRED = ['predictive', 'admin']
  const allRoutes = [...app.matchAll(/<Route path="([a-z-]+)"\s+element/g)].map(m => m[1]).filter(p => p !== 'collection')
  const routes = allRoutes.filter(p => !RETIRED.includes(p))

  it('groups the pages by what the staff does with them', () => {
    expect(NAV_GROUPS.map(g => g.label)).toEqual(['Equipos', 'Jugadores', 'Partido', 'Competición', 'Live', 'Informes'])
  })

  it('has an entry for every page of a collection and none for a page that does not exist', () => {
    const paths = NAV_ITEMS.map(i => i.subPath)
    expect(paths.filter(p => p !== '').sort()).toEqual([...routes].sort())
    expect(new Set(paths).size).toBe(paths.length)                      // a page is in ONE group
  })

  it('the live package is made by the app, not by a page of the web: no live-prep route or entry (issue #667)', () => {
    expect(routes).not.toContain('live-prep')
    expect(NAV_ITEMS.map(i => i.subPath)).not.toContain('live-prep')
  })

  it('the Administration page is gone (issue #724): its address goes to the home, the page is not imported and the web asks the server for none of its writes', () => {
    expect(app).not.toMatch(/import AdminPage/)
    expect(app).toMatch(/<Route\s+path="admin"\s+element=\{<Navigate to="\/" replace \/>\}/)
    expect(app).not.toMatch(/PrivateRoute requiredRole/)
  })

  it('the old predictive analysis is gone (#852): its old address goes to the preview of the match, which replaces it, and its page is not imported', () => {
    expect(NAV_ITEMS.map(i => i.subPath)).not.toContain('predictive')
    expect(app).not.toMatch(/import PredictivePage/)
    expect(app).toMatch(/<Route path="predictive"\s+element=\{<Navigate to="..\/previa"/)
    expect(allRoutes).toContain('predictive')
  })

  it('the preview of the match is in the group of the match, before the analysis of a played one, and needs the calendar of the competition to be published', () => {
    const group = NAV_GROUPS.find(g => g.label === 'Partido')!
    expect(group.items.map(i => i.subPath)).toEqual(['previa', 'matches'])
    expect(group.items[0].requires).toEqual({ section: 'calendar', dataset: 'forecast' })
    expect(app).toMatch(/<Route path="previa"\s+element=\{<RequirePublished/)
  })

  it('the simulation of the league has a group of its own, and like the preview it needs the calendar of the competition to be published', () => {
    const group = NAV_GROUPS.find(g => g.label === 'Competición')!
    expect(group.items.map(i => i.subPath)).toEqual(['simulacion'])
    expect(group.items[0].requires).toEqual({ section: 'calendar', dataset: 'forecast' })
    expect(app).toMatch(/<Route path="simulacion"\s+element=\{<RequirePublished/)
  })

  it('every entry says what it is for (the card of the hub)', () => {
    for (const item of NAV_ITEMS) expect(item.description.length, item.subPath || 'resumen').toBeGreaterThan(10)
  })
})
