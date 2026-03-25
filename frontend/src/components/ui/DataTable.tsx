/**
 * DataTable — TanStack Table v8 wrapper with:
 *   - Column sorting (click header)
 *   - Global search filter
 *   - Quartile cell coloring (pass quartiles prop)
 *   - Trend badge in cells (rendered via column meta)
 *   - Sticky first column (team/player name)
 *   - Loading skeleton
 *
 * Usage:
 *   <DataTable columns={columns} data={rows} quartiles={quartiles} />
 */
import { useRef, useMemo, useState } from 'react'
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
  type ColumnFiltersState,
  type Row,
} from '@tanstack/react-table'
import { ArrowUpDown, ArrowUp, ArrowDown, Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import ExportButton, { type ExportOptions } from '@/components/ui/ExportButton'
export interface QuartileMap {
  /** key = column id; value = [q1, q2, q3] thresholds for colour coding */
  [columnId: string]: [number, number, number] | undefined
}

interface Props<TData> {
  columns: ColumnDef<TData, unknown>[]
  data: TData[]
  /** Per-column quartile thresholds for cell coloring */
  quartiles?: QuartileMap
  /** Column IDs where lower is better (reversed quartile coloring) */
  reverseColumns?: string[]
  /** Show global search bar */
  searchable?: boolean
  searchPlaceholder?: string
  /** Loading state */
  loading?: boolean
  /** Export options */
  exportOptions?: Omit<ExportOptions, 'captureRef'>
  /** Optional row click handler */
  onRowClick?: (row: Row<TData>) => void
  className?: string
}

function quartileCellClass(
  value: unknown,
  thresholds: [number, number, number] | [number, number, number, number, number] | undefined,
  reverse: boolean,
): string {
  if (!thresholds || typeof value !== 'number') return ''
  // Support both [q1,q2,q3] and [min,q1,q2,q3,max]
  const [q1, q2, q3] = thresholds.length === 5 ? thresholds.slice(1) : thresholds
  if (!reverse) {
    if (value >= q3) return 'table-cell-q1'
    if (value >= q2) return 'table-cell-q2'
    if (value >= q1) return 'table-cell-q3'
    return 'table-cell-q4'
  } else {
    if (value <= q1) return 'table-cell-q1'
    if (value <= q2) return 'table-cell-q2'
    if (value <= q3) return 'table-cell-q3'
    return 'table-cell-q4'
  }
}

function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-3 py-2.5">
          <div className="h-3.5 rounded animate-pulse bg-surface-border/50" />
        </td>
      ))}
    </tr>
  )
}

export default function DataTable<TData>({
  columns,
  data,
  quartiles,
  reverseColumns = [],
  searchable = true,
  searchPlaceholder = 'Buscar…',
  loading = false,
  exportOptions,
  onRowClick,
  className,
}: Props<TData>) {
  const tableRef = useRef<HTMLTableElement>(null)
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [globalFilter, setGlobalFilter] = useState('')

  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnFilters, globalFilter },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  })

  const csvData = useMemo(
    () => exportOptions?.csvData ?? (data as Record<string, unknown>[]),
    [exportOptions, data],
  )

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {/* Toolbar */}
      {(searchable || exportOptions) && (
        <div className="flex items-center gap-3 flex-wrap">
          {searchable && (
            <div className="relative flex-1 min-w-[180px] max-w-xs">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-muted pointer-events-none" />
              <input
                value={globalFilter}
                onChange={e => setGlobalFilter(e.target.value)}
                placeholder={searchPlaceholder}
                className="input pl-8 text-xs py-1.5"
              />
            </div>
          )}
          {exportOptions && (
            <ExportButton
              {...exportOptions}
              csvData={csvData}
              captureRef={tableRef as React.RefObject<HTMLElement>}
              className="ml-auto"
            />
          )}
        </div>
      )}

      {/* Table wrapper */}
      <div className="overflow-x-auto rounded-card border border-surface-border">
        <table ref={tableRef} className="w-full min-w-[480px] text-sm border-collapse">
          <thead>
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id}>
                {hg.headers.map((header, i) => (
                  <th
                    key={header.id}
                    colSpan={header.colSpan}
                    className={cn(
                      'px-2 py-2.5 text-left text-xs font-medium text-ink-secondary',
                      'bg-surface-raised border-b border-surface-border select-none',
                      i === 0 && 'sticky left-0 z-10 bg-surface-raised',
                      header.column.getCanSort() && 'cursor-pointer hover:text-ink-primary',
                    )}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <span className="flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getCanSort() && (
                        <span className="text-ink-muted">
                          {header.column.getIsSorted() === 'asc'  && <ArrowUp className="w-3 h-3" />}
                          {header.column.getIsSorted() === 'desc' && <ArrowDown className="w-3 h-3" />}
                          {!header.column.getIsSorted()           && <ArrowUpDown className="w-3 h-3 opacity-30" />}
                        </span>
                      )}
                    </span>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <SkeletonRow key={i} cols={columns.length} />
                ))
              : table.getRowModel().rows.map(row => (
                  <tr
                    key={row.id}
                    onClick={() => onRowClick?.(row)}
                    className={`border-b border-surface-border/50 hover:bg-surface-hover transition-colors${onRowClick ? ' cursor-pointer' : ''}`}
                  >
                    {row.getVisibleCells().map((cell, i) => {
                      const colId = cell.column.id
                      const cellValue = cell.getValue()
                      const q = quartiles?.[colId]
                      const isReversed = reverseColumns.includes(colId)
                      const qClass = q ? quartileCellClass(cellValue, q, isReversed) : ''

                      return (
                        <td
                          key={cell.id}
                          className={cn(
                            'px-2 py-1.5 tabular-nums',
                            qClass ? '' : 'text-ink-primary',
                            i === 0 && 'sticky left-0 z-10 bg-surface-raised font-medium text-ink-primary',
                            qClass,
                          )}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      )
                    })}
                  </tr>
                ))
            }
          </tbody>
        </table>

        {!loading && table.getRowModel().rows.length === 0 && (
          <div className="py-12 text-center text-sm text-ink-secondary">
            Sin resultados para los filtros aplicados.
          </div>
        )}
      </div>

      {/* Row count */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <p className="text-xs text-ink-muted">
          {table.getRowModel().rows.length} filas
          {data.length !== table.getRowModel().rows.length && ` de ${data.length}`}
        </p>


      </div>
    </div>
  )
}
