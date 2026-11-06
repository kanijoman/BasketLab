/** Route guard (issue #780): the page of a section of `web-data` opens only where the competition has it published; otherwise the address goes back to the summary. */
import type { ReactNode } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import type { PageRequirement } from '@/lib/nav'
import { isOffered, usePublishedSections } from '@/lib/useVisibleNav'
import { dataSourceOf } from '@/datasource/switch'

export default function RequirePublished({ requires, children }: { requires: PageRequirement; children: ReactNode }) {
  const { collection } = useParams<{ collection?: string }>()
  const sections = usePublishedSections(collection, dataSourceOf(requires.dataset) === 'local')
  if (dataSourceOf(requires.dataset) === 'local' && sections === null) return null          // still finding out: neither the page nor a redirect
  return isOffered(requires, sections) ? <>{children}</> : <Navigate to=".." replace />
}
