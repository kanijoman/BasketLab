/**
 * The discreet notice of a stale external source (#884, PR C): «Datos de NCAA del 17/11: la última actualización falló.». It is shown under the header on the pages of an external competition only (a competition of
 * FEB or FBCYL has no source, and then nothing is even asked) and only when the source failed on its last run or its last good data is more than a day and a half old (`lib/sourceFreshness`). If the freshness cannot
 * be had it says nothing and breaks nothing. The tone is `warn`, the one of borderline data (docs/UI.md).
 */
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { TONE_PANEL } from '@/components/ui/tone'
import { freshnessNotice } from '@/lib/sourceFreshness'
import { loadSourceFreshness, sourceOf } from '@/webdata/client'

interface Props {
  /** The moment to compare with (tests); now by default. */
  now?: number
}

export default function SourceFreshnessNotice({ now }: Props) {
  const { collection } = useParams<{ collection?: string }>()
  const name = collection ? decodeURIComponent(collection) : ''
  const { data = [] } = useQuery({ queryKey: ['source-freshness'], queryFn: loadSourceFreshness, enabled: sourceOf(name) !== null, staleTime: 5 * 60_000, retry: false })
  const notice = freshnessNotice(name, data, now ?? Date.now())
  return notice ? <p role="status" className={`mb-3 rounded-lg border px-3 py-2 text-sm text-ink ${TONE_PANEL.warn}`}>{notice}</p> : null
}
