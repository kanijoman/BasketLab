/** The pages a competition offers (issue #780): the ones that need a section of `web-data` only appear once the publication has it for that competition.
 *  A page is deployed with the web, its data a while later (the publication takes up to an hour): until then it is hidden, not «coming soon». */
import { useEffect, useState } from 'react'
import { dataSourceOf } from '@/datasource/switch'
import { publishedSectionsOf } from '@/webdata/client'
import { NAV_GROUPS, type NavGroup, type PageRequirement } from './nav'

/** The sections `collection` has published, once the publication has been read (`null` while it is being read). */
export function usePublishedSections(collection: string | undefined, needed: boolean): Set<string> | null {
  const [found, setFound] = useState<{ collection: string; sections: Set<string> } | null>(null)
  useEffect(() => {
    if (!needed || !collection) return
    let current = true
    publishedSectionsOf(collection).then(sections => sections, () => new Set<string>()).then(sections => { if (current) setFound({ collection, sections }) })
    return () => { current = false }
  }, [collection, needed])
  return found && found.collection === collection ? found.sections : null
}

/** Whether a page with this requirement is offered: always with the API as its source (development), else only when the sections read so far include it. */
export function isOffered(requires: PageRequirement | undefined, sections: Set<string> | null): boolean {
  if (!requires || dataSourceOf(requires.dataset) !== 'local') return true
  return sections !== null && sections.has(requires.section)
}

const NEEDS_PUBLICATION = NAV_GROUPS.some(g => g.items.some(i => i.requires))

export function useVisibleNavGroups(collection: string | undefined): NavGroup[] {
  const sections = usePublishedSections(collection, NEEDS_PUBLICATION && NAV_GROUPS.some(g => g.items.some(i => i.requires && dataSourceOf(i.requires.dataset) === 'local')))
  return NAV_GROUPS.map(group => ({ ...group, items: group.items.filter(item => isOffered(item.requires, sections)) }))
}
