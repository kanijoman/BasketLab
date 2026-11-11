// The small texts of the preview page (#849).
import type { Court } from '@/forecast/winProb'

const DAYS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb']

/** `2026-11-15T18:00` -> `sáb 15/11 18:00` (the calendar is in Madrid time and is shown as it is). */
export function whenText(start: string | null): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2})/.exec(start ?? '')
  if (!m) return 'Fecha por confirmar'
  const day = DAYS[new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))).getUTCDay()]
  return `${day} ${m[3]}/${m[2]} ${m[4]}`
}

/** `6` -> `+6,0`; `-3.24` -> `−3,2` (a real minus sign, the decimal comma). */
export function signed(x: number, digits = 1): string {
  const text = Math.abs(x).toFixed(digits).replace('.', ',')
  return x < 0 && Number(text.replace(',', '.')) !== 0 ? `−${text}` : `+${text}`
}

export const courtText = (court: Court): string => (court === 'own' ? 'En casa' : court === 'rival' ? 'Fuera' : 'Campo neutral')
