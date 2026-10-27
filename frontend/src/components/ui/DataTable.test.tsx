import { render, screen, within } from '@testing-library/react'
import type { ColumnDef } from '@tanstack/react-table'
import { afterEach, describe, expect, it, vi } from 'vitest'
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

describe('DataTable quartile colours', () => {
  const rows = [{ team: 'A', v: 1 }, { team: 'B', v: 2 }, { team: 'C', v: 3 }, { team: 'D', v: 4 }]
  const columns: ColumnDef<(typeof rows)[number], unknown>[] = [{ id: 'team', accessorKey: 'team', header: 'Equipo' }, { id: 'v', accessorKey: 'v', header: 'V' }]
  const classes = () => rows.map(r => (screen.getByText(String(r.v)).className.match(/table-cell-q\d/) ?? ['none'])[0])

  it('colours the best to the worst with the thresholds it is given', () => {
    render(<DataTable columns={columns} data={rows} quartiles={{ v: [1.75, 2.5, 3.25] }} />)
    expect(classes()).toEqual(['table-cell-q4', 'table-cell-q3', 'table-cell-q2', 'table-cell-q1'])
  })

  it('does not colour a column whose thresholds are [0, 0, 0]: that is how «not enough values to split» is said (issue #601)', () => {
    render(<DataTable columns={columns} data={rows} quartiles={{ v: [0, 0, 0] }} />)
    expect(classes()).toEqual(['none', 'none', 'none', 'none'])
  })
})

// Issue #184: DataTable v2. Density, the states of the system (EmptyState, a Spinner that says it is loading) and, on a phone, every row as
// a card (the first column is its title and the rest go label: value), so a wide table needs no sideways scroll.
describe('DataTable v2 (issue #184)', () => {
  const rows = [{ team: 'León', pts: 70.5, reb: 38 }, { team: 'Zamora', pts: 64.1, reb: 41 }]
  const columns: ColumnDef<(typeof rows)[number], unknown>[] = [
    { id: 'team', accessorKey: 'team', header: 'Equipo' },
    { id: 'pts', accessorKey: 'pts', header: 'PTS' },
    { id: 'reb', accessorKey: 'reb', header: () => <span>Reb</span>, meta: { label: 'Rebotes' } },
  ]
  const phone = (matches: boolean) => vi.stubGlobal('matchMedia', (query: string) => ({ matches: matches && query.includes('max-width'), media: query,
    addEventListener: () => undefined, removeEventListener: () => undefined }))
  afterEach(() => vi.unstubAllGlobals())

  it.each([['compact', 'py-1'], ['comfortable', 'py-2.5']] as const)('density %s', (density, cls) => {
    render(<DataTable columns={columns} data={rows} searchable={false} density={density} />)
    expect(screen.getByText('León').closest('td')).toHaveClass(cls)
  })

  it('says it is loading, and says what to do when no row is left', () => {
    const { rerender } = render(<DataTable columns={columns} data={[]} searchable={false} loading />)
    expect(screen.getByRole('status', { name: 'Cargando la tabla' })).toBeInTheDocument()
    rerender(<DataTable columns={columns} data={[]} searchable={false} emptyMessage="Esta temporada aún no tiene partidos." />)
    expect(screen.getByText('Sin resultados')).toBeInTheDocument()
    expect(screen.getByText('Esta temporada aún no tiene partidos.')).toBeInTheDocument()
  })

  it('on a phone every row is a card: the first column is its title, the rest label and value', () => {
    phone(true)
    render(<DataTable columns={columns} data={rows} searchable={false} />)
    expect(document.querySelector('table')).toBeNull()
    const cards = screen.getAllByRole('listitem')
    expect(cards).toHaveLength(2)
    expect(within(cards[0]).getByRole('heading', { name: 'León' })).toBeInTheDocument()
    expect(within(cards[0]).getByText('PTS').nextElementSibling).toHaveTextContent('70.5')
    expect(within(cards[0]).getByText('Rebotes').nextElementSibling).toHaveTextContent('38')   // a header that is not text says meta.label
  })

  it('on a wide screen it stays a table', () => {
    phone(false)
    render(<DataTable columns={columns} data={rows} searchable={false} />)
    expect(document.querySelector('table')).not.toBeNull()
  })
})
