/**
 * Change of competition from the header (issue #191, U4): the same page of the other collection (`/LF2_A/lineups` → `/LF2_B/lineups`).
 * With a single competition there is nothing to choose and it renders nothing. The query key and its answer are the home page's (#605).
 */
import { useQuery } from '@tanstack/react-query'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { getCollectionList } from '@/api/client'
import { Select } from '@/components/ui/Field'

const label = (c: { competition: string; season: string; group: string }) => [c.competition, c.season, c.group && `Grupo ${c.group}`].filter(Boolean).join(' · ')

export default function CollectionSwitcher() {
  const { collection } = useParams<{ collection?: string }>()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { data: collections = [] } = useQuery({ queryKey: ['collections-list'], queryFn: getCollectionList, staleTime: 30_000 })

  if (!collection || collections.length < 2) return null
  const current = decodeURIComponent(collection)

  function change(next: string) {
    const rest = pathname.split('/').slice(2).join('/')        // the page inside the collection ('' = the summary)
    navigate(`/${encodeURIComponent(next)}${rest ? `/${rest}` : ''}`)
  }

  return (
    <Select
      aria-label="Competición"
      value={current}
      onChange={e => change(e.target.value)}
      options={collections.map(c => ({ value: c.name, label: label(c) || c.name }))}
      className="max-w-[16rem] truncate py-1 text-xs"
    />
  )
}
