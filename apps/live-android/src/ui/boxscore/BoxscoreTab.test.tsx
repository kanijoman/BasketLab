import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { BoxscoreEntry, LastStat, Snapshot, SnapshotPlayer } from '../../engine/types'
import BoxscoreTab from './BoxscoreTab'

afterEach(cleanup)

const stats = (over: Partial<SnapshotPlayer['stats']> = {}) => ({ fg2m: 0, fg2a: 0, fg3m: 0, fg3a: 0, ftm: 0, fta: 0, orb: 0, drb: 0, tov: 0, stl: 0, ast: 0, blk: 0, ...over })
const player = (name: string, team: string, over: Partial<SnapshotPlayer> = {}): SnapshotPlayer =>
  ({ name, team_id: team, on_court: false, minutes: 0, pf: 0, pts: 0, pm: 0, fd: 0, stats: stats(), ...over })
const OWN = { id: 'A', name: 'CULTURAL Y DEPORTIVA LEONESA' }
const RIVAL = { id: 'B', name: 'MELILLA CIUDAD DEL DEPORTE' }

const snapshot = (last: LastStat | null = null): Snapshot => ({
  period: 1, remaining: 300, elapsed: 300, score: { A: 7, B: 4 }, home_id: 'B',
  teams: { A: { name: OWN.name, fouls_game: 1, stats: { ...stats({ fg2m: 2, fg2a: 3 }), tov_team: 0, pts: 7 } }, B: { name: RIVAL.name, fouls_game: 0, stats: { ...stats(), tov_team: 0, pts: 4 } } },
  players: {
    p1: player('A. PRIMERA', 'A', { on_court: true, minutes: 300, pts: 7, stats: stats({ fg2m: 2, fg2a: 3 }) }),
    p2: player('B. BANQUILLO', 'A', { minutes: 0 }),
    r1: player('R. VISITANTE', 'B', { on_court: true, minutes: 300, pts: 4 }),
  },
  last_stat: last,
}) as unknown as Snapshot

const ENTRIES: Record<string, BoxscoreEntry> = {
  p1: { val: 5, adv: { usage: 30, orating: 100.5, drating: 90, net_rtg: 10, efg: 66.7, ts: 70, ftr: 0, three_pr: 0, ast_pct: 0, tov_pct: 0, stl_pct: 0, blk_pct: 0, drb_pct: 0, orb_pct: 0, pie: 40 }, dev: { pts: 0.9, tov: -0.3, ast: 0 } },
}

const last = (over: Partial<LastStat> = {}): LastStat => ({ seq: 1, player_id: 'p1', team_id: 'A', keys: ['pts', 'fg2m', 'fg2a'], also: [], ...over })
const view = (props: Partial<Parameters<typeof BoxscoreTab>[0]> = {}) => <BoxscoreTab snapshot={snapshot()} entries={ENTRIES} own={OWN} rival={RIVAL} homeId="B" {...props} />
const rowOf = (name: string) => screen.getByText(name).closest('tr')!
const team = () => screen.getByRole('radiogroup', { name: 'Equipo' })

describe('BoxscoreTab (issue #593)', () => {
  it('opens on the own team, with a row per player and the totals', () => {
    render(view())
    expect(screen.getByRole('table', { name: /CULTURAL Y DEPORTIVA LEONESA/ })).toBeTruthy()
    expect(screen.getByText('A. PRIMERA')).toBeTruthy()
    expect(screen.queryByText('R. VISITANTE')).toBeNull()
    expect(screen.getByText('Totales')).toBeTruthy()
    expect(rowOf('A. PRIMERA').querySelector('td[data-col="t2"]')?.textContent).toBe('2/3')
  })

  it('the two teams are two options, the local one first, and choosing the other shows its players', () => {
    render(view())
    const options = within(team()).getAllByRole('radio')
    expect(options.map(o => o.textContent)).toEqual([expect.stringContaining('MELILLA'), expect.stringContaining('CULTURAL')])
    fireEvent.click(options[0])
    expect(screen.getByText('R. VISITANTE')).toBeTruthy()
    expect(screen.queryByText('A. PRIMERA')).toBeNull()
  })

  it('normal and advanced are two options and the advanced table has the figures of the web instead of the shooting', () => {
    render(view())
    expect(screen.getByRole('columnheader', { name: 'T2' })).toBeTruthy()
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Estadística' })).getByRole('radio', { name: 'Avanzada' }))
    for (const label of ['Usg%', 'ORtg', 'DRtg', 'NetRtg', 'eFG%', 'TS%', 'FTr', '3Pr', '%AST', '%TO', '%ROB', '%TAP', '%RD', '%RO', 'PIE%']) {
      expect(screen.getByRole('columnheader', { name: label })).toBeTruthy()
    }
    expect(screen.queryByRole('columnheader', { name: /^T2/ })).toBeNull()
    expect(within(rowOf('A. PRIMERA')).getByText('30,0')).toBeTruthy()
  })

  it('the player on court is marked for everybody, not only by colour', () => {
    render(view())
    expect(within(rowOf('A. PRIMERA')).getByRole('img', { name: 'En pista' })).toBeTruthy()
    expect(within(rowOf('B. BANQUILLO')).queryByRole('img', { name: 'En pista' })).toBeNull()
  })

  it('the first column is the one that stays when the table is moved sideways', () => {
    render(view())
    expect(rowOf('A. PRIMERA').firstElementChild?.className).toContain('bx-name')
    expect(screen.getByRole('table').parentElement?.className).toContain('bx-scroll')
  })

  describe('against his own average', () => {
    const cell = (column: string) => rowOf('A. PRIMERA').querySelector(`td[data-col="${column}"]`)!

    it('a column above it is green and below it red, with the words and the arrow when it is far', () => {
      render(view())
      expect(cell('pts').getAttribute('data-dev')).toBe('up')
      expect(cell('pts').getAttribute('title')).toMatch(/por encima de su media/i)
      expect(cell('pts').textContent).toContain('▲')
      expect(cell('tov').getAttribute('data-dev')).toBe('down')
      expect(cell('tov').textContent).not.toContain('▼')                       // -0.3 is not far
    })

    it('what is at his average or has none is not coloured', () => {
      render(view())
      expect(cell('ast').getAttribute('data-dev')).toBeNull()                  // 0: exactly his average
      expect(cell('min').getAttribute('data-dev')).toBeNull()
      expect(rowOf('B. BANQUILLO').querySelector('[data-dev]')).toBeNull()
    })

    it('the cell says its intensity as a number the stylesheet turns into colour', () => {
      render(view())
      expect(cell('pts').getAttribute('style')).toContain('--dev-abs: 0.9')
    })

    it('there is a legend that says it', () => {
      render(view())
      expect(screen.getByText(/verde: mejor que su media/i)).toBeTruthy()
    })
  })

  describe('the last action', () => {
    it('does not flash what was already there when the tab opens', () => {
      const { container } = render(view({ snapshot: snapshot(last()) }))
      expect(container.querySelector('.bump')).toBeNull()
      expect(container.querySelector('.bx-hit')).toBeNull()
    })

    it('flashes the row and the cells of the new action, once', () => {
      const { rerender, container } = render(view({ snapshot: snapshot(last()) }))
      rerender(view({ snapshot: snapshot(last({ seq: 2 })) }))
      const row = rowOf('A. PRIMERA')
      expect(row.className).toContain('bx-hit')
      expect([...row.querySelectorAll('td.bump')].map(c => c.getAttribute('data-col'))).toEqual(['pts', 't2', 'tc'])
      expect(container.querySelectorAll('tr.bx-hit').length).toBe(1)
    })

    it('says there is news in the other team when the action is not in the one being seen', () => {
      const { rerender } = render(view({ snapshot: snapshot(last()) }))
      rerender(view({ snapshot: snapshot(last({ seq: 2, player_id: 'r1', team_id: 'B', keys: ['ast'] })) }))
      const other = within(team()).getByRole('radio', { name: /MELILLA/ })
      expect(within(other).getByText(/novedad/i)).toBeTruthy()
      fireEvent.click(other)
      expect(within(team()).queryByText(/novedad/i)).toBeNull()
    })
  })

  it('without a match yet it says so instead of an empty table', () => {
    render(view({ snapshot: undefined }))
    expect(screen.getByText(/sin partido/i)).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('a player with nothing played has dashes and no figures invented', () => {
    render(view())
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Estadística' })).getByRole('radio', { name: 'Avanzada' }))
    expect(within(rowOf('B. BANQUILLO')).getAllByText('—').length).toBeGreaterThan(5)
  })
})
