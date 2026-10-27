/**
 * A table on a phone (issue #184): every row is a card, the first column its title and the rest «label: value», so a wide table needs no
 * sideways scroll. The label of a value is `meta.label`, or the header of its column as the table draws it (with its tooltip), after the
 * name of its group. Used by DataTable.
 */
import type { ReactNode } from 'react'
import { flexRender, type Cell, type Header, type Row, type Table } from '@tanstack/react-table'
import { cn } from '@/lib/utils'

function label<TData>(cell: Cell<TData, unknown>, headers: Map<string, Header<TData, unknown>>): ReactNode {
  const { column } = cell
  const header = headers.get(column.id)
  const own = column.columnDef.meta?.label ?? (header ? flexRender(column.columnDef.header, header.getContext()) : column.id)
  const group = column.parent?.columnDef.header
  return typeof group === 'string' && group ? <>{group} · {own}</> : own
}

interface Props<TData> {
  table: Table<TData>
  cellClass: (cell: Cell<TData, unknown>) => string
  onRowClick?: (row: Row<TData>) => void
}

export default function DataTableCards<TData>({ table, cellClass, onRowClick }: Props<TData>) {
  const headers = new Map(table.getFlatHeaders().map(h => [h.column.id, h]))
  return (
    <ul role="list" className="space-y-2">
      {table.getRowModel().rows.map(row => {
        const [first, ...rest] = row.getVisibleCells()
        return (
          <li key={row.id} onClick={() => onRowClick?.(row)} className={cn('card p-3', onRowClick && 'cursor-pointer')}>
            <h3 className="mb-2 text-sm font-semibold text-ink">{first && flexRender(first.column.columnDef.cell, first.getContext())}</h3>
            <dl className="grid grid-cols-[repeat(auto-fill,minmax(min(9rem,100%),1fr))] gap-x-4 gap-y-1 text-xs">
              {rest.map(cell => (
                <div key={cell.id} className="flex items-baseline justify-between gap-2 border-b border-line/40 py-0.5">
                  <dt className="truncate text-ink-muted">{label(cell, headers)}</dt>
                  <dd className={cn('rounded px-1 text-right tabular-nums text-ink', cellClass(cell))}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</dd>
                </div>
              ))}
            </dl>
          </li>
        )
      })}
    </ul>
  )
}
