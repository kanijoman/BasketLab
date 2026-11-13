/**
 * Change of competition from the header (issues #191, #761): the same page of the other collection (`/LF2_A/lineups` → `/LF2_B/lineups`), chosen by the levels of the data
 * (ámbito, temporada, competición, grupo) and always showing the same ones (#912; the group only when it has a phase or a group to name). With a single competition there is nothing to choose and it renders nothing.
 * The query key and its answer are the home page's (#605).
 */
import { useQuery } from '@tanstack/react-query'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { getCollectionList } from '@/api/client'
import CollectionPicker from '@/components/CollectionPicker'
import { selectionOf } from '@/lib/collectionPicker'

export default function CollectionSwitcher() {
  const { collection } = useParams<{ collection?: string }>()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { data: collections = [] } = useQuery({ queryKey: ['collections-list'], queryFn: getCollectionList, staleTime: 30_000 })

  if (!collection || collections.length < 2) return null
  const current = decodeURIComponent(collection)
  const info = collections.find(c => c.name === current)

  function change(next: string) {
    const rest = pathname.split('/').slice(2).join('/')        // the page inside the collection ('' = the summary)
    navigate(`/${encodeURIComponent(next)}${rest ? `/${rest}` : ''}`)
  }

  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <CollectionPicker list={collections} value={info ? selectionOf(info) : {}} compact onChange={(_, picked) => picked && picked.name !== current && change(picked.name)} />
    </div>
  )
}
