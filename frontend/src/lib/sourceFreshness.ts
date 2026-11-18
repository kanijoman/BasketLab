// The notice of an external source that is not fresh (#884, PR C): discreet, with the date of the data. It exists only when there is something to say: the last run of the source failed, or its last good data is
// more than a day and a half old (the daily run did not happen). A fine source says nothing, a competition of FEB or FBCYL has no source, and a source the publication does not mention is no reason to alarm anybody.
import { sourceOf } from '@/webdata/sources'
import type { SourceFreshness } from '@/webdata/contract.generated'

/** The daily run of a source is late after this many hours: a day and a half. */
export const STALE_AFTER_HOURS = 36

/** `17/11`: the day by its UTC date, so the text is the same in every time zone. */
const day = (stamp: string): string => `${stamp.slice(8, 10)}/${stamp.slice(5, 7)}`

/** The text of the notice of the competition `collection`, or `null` when its source is fine or it has none. `now` is a timestamp in milliseconds. */
export function freshnessNotice(collection: string, freshness: SourceFreshness[], now: number): string | null {
  const source = sourceOf(collection)
  const entry = source ? freshness.find(f => f.source === source) : undefined
  if (!source || !entry) return null
  const name = source.toUpperCase()
  if (!entry.ok) return entry.last_ok ? `Datos de ${name} del ${day(entry.last_ok)}: la última actualización falló.` : `La última actualización de ${name} falló.`
  const age = entry.last_ok ? (now - Date.parse(entry.last_ok)) / 3600_000 : Infinity
  return age > STALE_AFTER_HOURS && entry.last_ok ? `Datos de ${name} del ${day(entry.last_ok)}.` : null
}
