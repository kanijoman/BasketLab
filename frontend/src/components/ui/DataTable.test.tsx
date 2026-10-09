import { render, screen, within } from '@testing-library/react'
import type { ColumnDef } from '@tanstack/react-table'
import { describe, expect, it } from 'vitest'
import DataTable from './DataTable'

interface Row { name: string; a: number; b: number; c: number }
const DATA: Row[] = [{ name: 'Equipo A', a: 1, b: 2, c: 3 }]

const FLAT: ColumnDef<Row, unknown>[] = [
  { id: 'name', accessorKey: 'name', header: 'Equipo' },
  { id: 'a', accessorKey: 'a', header: 'A' },
]

const GROUPED: ColumnDef<Row, unknown>[] = [
  { id: 'name', accessorKey: 'name', header: 'Equipo' },
  {
    id: 'grp', header: 'Rápidas',
    columns: [
      { id: 'b', accessorKey: 'b', header: '%' },
      { id: 'c', accessorKey: 'c', header: 'OER' },
    ],
  },
]

describe('DataTable header groups', () => {
  it('a table without groups keeps a single header row', () => {
    render(<DataTable columns={FLAT} data={DATA} searchable={false} />)
    expect(document.querySelectorAll('thead tr')).toHaveLength(1)
  })

  it('renders the group label spanning its sub-columns above them', () => {
    render(<DataTable columns={GROUPED} data={DATA} searchable={false} />)
    const rows = document.querySelectorAll('thead tr')
    expect(rows).toHaveLength(2)
    const group = within(rows[0] as HTMLElement).getByText('Rápidas').closest('th')!
    expect(group).toHaveAttribute('colspan', '2')
    expect(within(rows[1] as HTMLElement).getByText('%')).toBeTruthy()
    expect(within(rows[1] as HTMLElement).getByText('OER')).toBeTruthy()
    expect(within(rows[1] as HTMLElement).getByText('Equipo')).toBeTruthy()
  })

  it('does not repeat the team label in the empty placeholder above it', () => {
    render(<DataTable columns={GROUPED} data={DATA} searchable={false} />)
    expect(screen.getAllByText('Equipo')).toHaveLength(1)
  })

  it('honours a smaller default column size', () => {
    render(<DataTable columns={GROUPED} data={DATA} searchable={false} defaultColumnSize={60} />)
    expect((screen.getByText('%').closest('th') as HTMLElement).style.width).toBe('60px')
  })
})
