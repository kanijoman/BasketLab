import type { RowData } from '@tanstack/react-table'

// What the columns of the web say about themselves (TanStack's ColumnMeta is ours to extend).
declare module '@tanstack/react-table' {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    /** The name of the column where its header is not plain text: the cards of a table on a phone (issue #184) */
    label?: string
    /** Lower is better (the quartile colours are reversed) */
    reverse?: boolean
  }
}
