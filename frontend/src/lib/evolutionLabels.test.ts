import { describe, expect, it } from 'vitest'
import { seriesLabel } from './evolutionLabels'

// The series of the chart of Evolución are named by team ID (`<id>_raw`, `<id>_avg`, `<id>_cum`): what the staff reads under the chart and in the
// tooltip is the NAME of the team (feedback of 28/10/2026: «aparece un código»), never the id.
const NAMES: Record<string, string> = { '982047': 'Recoletas Zamora', '1008857': 'Cultural Leonesa' }
const name = (id: string) => NAMES[id] ?? id

describe('seriesLabel (Evolución)', () => {
  it.each([
    ['982047_raw', 'Recoletas Zamora (partido)'],
    ['982047_avg', 'Recoletas Zamora (media 5J)'],
    ['982047_cum', 'Recoletas Zamora (acumulado)'],
    ['comp_rolling', 'Liga (media 5J)'],
    ['comp_cumulative', 'Liga (acumulado)'],
  ])('%s → %s', (key, expected) => {
    expect(seriesLabel(key, name, 5)).toBe(expected)
  })

  it('never shows the id of a team that is in the list', () => {
    for (const id of Object.keys(NAMES)) for (const suffix of ['raw', 'avg', 'cum']) expect(seriesLabel(`${id}_${suffix}`, name, 3)).not.toContain(id)
  })

  it('two teams in the same chart are told apart in the tooltip: each line names its team', () => {
    const labels = ['982047_avg', '1008857_avg'].map(key => seriesLabel(key, name, 5))
    expect(new Set(labels).size).toBe(2)
  })

  it('a team the list does not have yet is shown by its id rather than by nothing (the list loads after the first chart)', () => {
    expect(seriesLabel('555_raw', name, 5)).toBe('555 (partido)')
  })
})
