import { describe, expect, it } from 'vitest'
import { activeFilters, byMinutes, withoutFilter } from './activeFilters'
import { NO_FILTERS, type SearchFilters } from './search'

const f = (patch: Partial<SearchFilters>): SearchFilters => ({ ...NO_FILTERS, ...patch })

/** The filters that are on, as chips that can be taken off one by one (#1008): what the staff sees on a phone when the panel is closed. */
describe('the active filters', () => {
  it('are none when nothing is asked', () => {
    expect(activeFilters(NO_FILTERS)).toEqual([])
  })

  it('say each thing asked in the words of the panel, in a fixed order, one chip per filter', () => {
    const chips = activeFilters(f({ text: 'ana', ageMin: 18, ageMax: 21, heightMin: 175, groups: ['G', 'C'], metric: 'pts', pctMin: 80, onlyEligible: true, includeUnknown: true }))
    expect(chips.map(c => c.key)).toEqual(['text', 'age', 'height', 'groups', 'metric', 'eligible', 'unknown'])
    expect(chips.map(c => c.label)).toEqual([
      'Nombre: ana', 'Edad: 18 a 21', 'Altura: desde 175 cm', 'Posición: bases y escoltas, pívots', 'Puntos / 40 desde el percentil 80', 'Solo con minutos suficientes', 'Con los que no tienen el dato',
    ])
  })

  it('say a one-sided range as «desde» or «hasta», and a metric without a threshold as just the metric', () => {
    expect(activeFilters(f({ ageMax: 20 })).map(c => c.label)).toEqual(['Edad: hasta 20'])
    expect(activeFilters(f({ heightMin: 180, heightMax: 190 })).map(c => c.label)).toEqual(['Altura: 180 a 190 cm'])
    expect(activeFilters(f({ metric: 'ast' })).map(c => c.label)).toEqual(['Asistencias / 40'])
  })

  it('count a zero as a filter (age 0 is a real limit, not «nothing»)', () => {
    expect(activeFilters(f({ ageMin: 0 })).map(c => c.label)).toEqual(['Edad: desde 0'])
  })

  it('leave only the others on when one is taken off, and the percentile goes with its metric', () => {
    const all = f({ text: 'ana', ageMin: 18, ageMax: 21, metric: 'pts', pctMin: 80, groups: ['G'] })
    expect(withoutFilter(all, 'age')).toEqual({ ...all, ageMin: null, ageMax: null })
    expect(withoutFilter(all, 'metric')).toEqual({ ...all, metric: '', pctMin: null })
    expect(withoutFilter(all, 'groups').groups).toEqual([])
    expect(withoutFilter(all, 'text').text).toBe('')
    expect(activeFilters(withoutFilter(withoutFilter(all, 'age'), 'metric')).map(c => c.key)).toEqual(['text', 'groups'])
  })

  it('does not change what it is given', () => {
    const all = f({ ageMin: 18, groups: ['G'] })
    const copy = JSON.parse(JSON.stringify(all))
    withoutFilter(all, 'groups'); activeFilters(all)
    expect(all).toEqual(copy)
  })
})

describe('the order of the list', () => {
  it('goes by minutes played, the most first, and a tie by name and team so the order never depends on the input', () => {
    const row = (name: string, team: string, minutes: number) => ({ full_name: null, name, team_name: team, minutes }) as never
    const rows = [row('B', 't', 100), row('A', 't', 100), row('C', 't', 500), row('A', 's', 100)]
    const sorted = byMinutes(rows)
    expect(sorted.map((r: { name: string; team_name: string }) => `${r.name}${r.team_name}`)).toEqual(['Ct', 'As', 'At', 'Bt'])
    expect(byMinutes([...rows].reverse())).toEqual(sorted)
    expect(rows[0]).toBe(rows[0])
  })
})
