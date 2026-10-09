import { render, screen } from '@testing-library/react'
import type { ColumnDef } from '@tanstack/react-table'
import { describe, expect, it } from 'vitest'
import type { PossessionStat } from '@/api/client'
import { ALL_VIEW_KEYS, REVERSE_COLS, VIEWS, buildCols, csvColumns, type PossessionView } from './columns'

type Col = ColumnDef<PossessionStat, unknown> & { columns?: Col[] }

/** Leaf column ids of a (possibly grouped) column tree, in display order. */
function leaves(cols: Col[]): string[] {
  return cols.flatMap(c => (c.columns ? leaves(c.columns) : [String(c.id)]))
}

describe('possession views', () => {
  it('the summary view shows the basic pace/efficiency columns only', () => {
    expect(leaves(buildCols('summary', null) as Col[])).toEqual([
      'team_name', 'total_games', 'possessions_per_game', 'pace', 'oer', 'der', 'net_rating',
    ])
  })

  it('the own-style view groups fast/medium/slow with % and OER', () => {
    const cols = buildCols('own', null) as Col[]
    expect(leaves(cols)).toEqual([
      'team_name', 'avg_duration', 'est_possessions_per_game',
      'pct_fast', 'oer_fast', 'pct_medium', 'oer_medium', 'pct_slow', 'oer_slow',
    ])
    expect(cols.filter(c => c.columns).map(c => c.header)).toEqual(['Rápidas', 'Medias', 'Lentas'])
  })

  it('the rival view mirrors the own-style one with the rival columns', () => {
    expect(leaves(buildCols('rival', null) as Col[])).toEqual([
      'team_name', 'rival_avg_duration', 'rival_pace_differential',
      'rival_pct_fast', 'rival_oer_fast', 'rival_pct_medium', 'rival_oer_medium', 'rival_pct_slow', 'rival_oer_slow',
    ])
  })

  it('every view fits without horizontal scroll: at most 9 columns', () => {
    for (const view of VIEWS.map(v => v.key)) expect(leaves(buildCols(view, null) as Col[]).length).toBeLessThanOrEqual(9)
  })

  it('no metric of the old 22-column table is lost: the views together cover all of them', () => {
    const old = [
      'team_name', 'total_games', 'possessions_per_game', 'pace', 'oer', 'der', 'net_rating',
      'avg_duration', 'pct_fast', 'pct_medium', 'pct_slow', 'oer_fast', 'oer_medium', 'oer_slow', 'est_possessions_per_game',
      'rival_pct_fast', 'rival_pct_medium', 'rival_pct_slow', 'rival_oer_fast', 'rival_oer_medium', 'rival_oer_slow',
      'rival_avg_duration', 'rival_pace_differential',
    ]
    const shown = new Set(VIEWS.flatMap(v => leaves(buildCols(v.key, null) as Col[])))
    expect(old.filter(k => !shown.has(k))).toEqual([])
  })

  it('the CSV keeps every column whatever the active view is', () => {
    const keys = csvColumns().map(c => c.key)
    expect(keys).toHaveLength(23)
    expect(keys).toEqual(expect.arrayContaining(ALL_VIEW_KEYS))
    expect(csvColumns().find(c => c.key === 'pct_fast')?.label).toBe('% Rápidas')
  })

  it('lower-is-better columns keep their reversed quartile colours', () => {
    expect(REVERSE_COLS).toEqual(expect.arrayContaining(['der', 'pct_slow', 'rival_oer_fast', 'rival_pace_differential']))
  })
})

describe('team cell (regression: the team name was cut without any hint)', () => {
  const NAME = 'MIPELLETYMAS B.F. LEON CON UN NOMBRE MUY LARGO'

  it('shows the full name in its title and can wrap instead of clipping', () => {
    const team = (buildCols('summary', null) as Col[])[0]
    const Cell = team.cell as (ctx: unknown) => JSX.Element
    render(Cell({ getValue: () => NAME, row: { original: { team_name: NAME, team_id: '1008631' } } }))
    const label = screen.getByText(NAME)
    expect(label).toHaveAttribute('title', NAME)
    expect(label.className).toContain('line-clamp-2')
    expect(label.className).not.toContain('whitespace-nowrap')
    expect(team.size).toBeGreaterThanOrEqual(220)
  })
})

describe('views', () => {
  it('lists Resumen, Estilo propio and Rival', () => {
    expect(VIEWS.map(v => v.label)).toEqual(['Resumen', 'Estilo propio', 'Rival'])
    const first: PossessionView = VIEWS[0].key
    expect(first).toBe('summary')
  })
})
