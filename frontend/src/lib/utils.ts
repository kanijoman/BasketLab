/** Utility helpers shared across components. */
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge Tailwind classes safely, resolving conflicts.
 * Requires: npm i clsx tailwind-merge
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/** Format a number to N decimal places, returning '—' for null/undefined/NaN. */
export function fmt(
  value: number | null | undefined,
  decimals = 1,
): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(decimals)
}

/** Format a percentage (0–1 or 0–100 input, always outputs 0–100%). */
export function fmtPct(
  value: number | null | undefined,
  decimals = 1,
  alreadyPercent = true,
): string {
  if (value == null || Number.isNaN(value)) return '—'
  const v = alreadyPercent ? value : value * 100
  return `${v.toFixed(decimals)}%`
}

/** Return Tailwind class for quartile coloring (Q1 best by default). */
export function quartileClass(
  value: number,
  q1: number,
  q2: number,
  q3: number,
  reverse = false,
): string {
  // reverse=true: lower value is better (TOV, fouls…)
  const [best, good, bad, worst] = reverse
    ? [q1, q2, q3, Infinity]
    : [-Infinity, q1, q2, q3]

  if (!reverse && value <= q1) return 'table-cell-q1'
  if (!reverse && value <= q2) return 'table-cell-q2'
  if (!reverse && value <= q3) return 'table-cell-q3'
  if (!reverse && value > q3)  return 'table-cell-q4'

  if (reverse && value <= q1)  return 'table-cell-q1'
  if (reverse && value <= q2)  return 'table-cell-q2'
  if (reverse && value <= q3)  return 'table-cell-q3'
  return 'table-cell-q4'

  // suppress unused warnings
  void best; void good; void bad; void worst
}
