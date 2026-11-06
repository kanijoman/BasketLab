/** Percentages of the assist connections (issue #773): whole numbers, `—` when there is nothing to divide. */
export const pct = (value: number | null | undefined): string => (value == null ? '—' : `${Math.round(value)}%`)

export const plural = (n: number, one: string, many: string): string => `${n} ${n === 1 ? one : many}`
