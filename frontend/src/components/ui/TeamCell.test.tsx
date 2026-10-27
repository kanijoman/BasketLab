/// <reference types="node" />
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import DataTable from './DataTable'
import TeamCell, { TEAM_COLUMN_SIZE, teamColumn } from './TeamCell'

// Issue #184: the team column of the possessions table (#182) liked: logo, the name in up to two lines and the full name in the
// tooltip, never cut without a hint. Every table with a team uses it now, with its width, from ONE place.
describe('TeamCell (issue #184)', () => {
  it('shows the logo and the name, whole in its tooltip', () => {
    const { container } = render(<TeamCell name="CLUB BALONCESTO ARIDANE LA PALMA ISLA BONITA" teamId="123" />)
    expect(screen.getByTitle('CLUB BALONCESTO ARIDANE LA PALMA ISLA BONITA')).toHaveClass('line-clamp-2')
    expect(container.querySelector('img')?.getAttribute('src')).toContain('123')
  })

  it('without an id, or when the logo does not load, it is the name alone (no broken image)', () => {
    const { container, rerender } = render(<TeamCell name="León" />)
    expect(container.querySelector('img')).toBeNull()
    rerender(<TeamCell name="León" teamId="9" />)
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('León')).toBeInTheDocument()
  })

  it('compact: the logo only, with the name as its tooltip and text alternative; three letters when there is no logo', () => {
    const { container, rerender } = render(<TeamCell name="Cultural Leonesa" teamId="7" compact />)
    expect(screen.getByRole('img', { name: 'Cultural Leonesa' })).toHaveAttribute('title', 'Cultural Leonesa')
    rerender(<TeamCell name="Cultural Leonesa" compact />)
    expect(container.textContent).toBe('CUL')
    expect(screen.getByTitle('Cultural Leonesa')).toBeInTheDocument()
  })
})

describe('teamColumn (issue #184)', () => {
  interface Row { team_name: string; team_id?: string; pts: number }
  const ROWS: Row[] = [{ team_name: 'Zamora', team_id: '2', pts: 70 }, { team_name: 'Avilés', pts: 80 }]

  it('is the team column of every table: its id, its header, its width and the TeamCell with the logo of the row', () => {
    const column = teamColumn<Row>()
    expect(column).toMatchObject({ id: 'team_name', header: 'Equipo', size: TEAM_COLUMN_SIZE, enableSorting: true })
    expect(TEAM_COLUMN_SIZE).toBe(240)
    const { container } = render(<DataTable columns={[column, { id: 'pts', accessorKey: 'pts', header: 'PTS' }]} data={ROWS} searchable={false} />)
    expect(screen.getByTitle('Zamora')).toBeInTheDocument()
    expect(container.querySelectorAll('tbody img')).toHaveLength(1)
  })

  it('compact: a narrow column without header for the logo next to a player', () => {
    expect(teamColumn<Row>({ compact: true })).toMatchObject({ id: 'team_name', header: '', size: 42 })
  })

  // the guard: a page that writes its own team column again (with its own width, cutting the name) fails here
  it('no page defines its own team column', () => {
    const src = join(__dirname, '..', '..')
    const files = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory()
      ? files(join(dir, e.name)) : /\.tsx?$/.test(e.name) && !/\.test\./.test(e.name) ? [join(dir, e.name)] : [])
    const own = files(src).filter(f => !f.endsWith('TeamCell.tsx') && /id: 'team_name'/.test(readFileSync(f, 'utf8')))
    expect(own.map(f => relative(src, f).replace(/\\/g, '/'))).toEqual([])
  })
})
