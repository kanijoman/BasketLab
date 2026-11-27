/** Route guard (issues #780, #1100): the page of a section of `web-data` opens only where the competition has it published. Where it has not (the origin of the data does not bring it, or it is
 *  not published yet) the address says so, with a way back, instead of an error, an empty page or a silent redirect. */
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import PageHeader from '@/components/ui/PageHeader'
import type { PageRequirement } from '@/lib/nav'
import { isOffered, usePublishedSections } from '@/lib/useVisibleNav'

export default function RequirePublished({ requires, children }: { requires: PageRequirement; children: ReactNode }) {
  const { collection } = useParams<{ collection?: string }>()
  const sections = usePublishedSections(collection, true)
  if (sections === null) return null          // still finding out: neither the page nor the notice
  if (isOffered(requires, sections)) return <>{children}</>
  return (
    <div className="space-y-3">
      <PageHeader title="No disponible para esta competición" />
      <p className="text-sm text-ink-muted">El origen de los datos no lo trae o todavía no está publicado.</p>
      <Link to={`/${collection ?? ''}`} className="text-sm text-secondary-text underline">Volver al resumen</Link>
    </div>
  )
}
