/** The players of a team that have left it (#1082): the baja of his line for this team in the FEB's «Trayectoria» is already reached. It comes with the published images of the team (`loadWebImages`),
 *  so only the web data of the FEB has it. Never hides anybody for not knowing: no publication, no key, FBCYL or a failed read give an empty set. */
import { useQuery } from '@tanstack/react-query'
import { dataSourceOf } from '@/datasource/switch'
import { hasLeftTeam } from '@/lib/playerAvailability'
import { loadWebImages } from '@/webdata/client'

const NOBODY: ReadonlySet<string> = new Set()

export function useLeftPlayers(collection: string | undefined, teamId: string): ReadonlySet<string> {
  const enabled = Boolean(collection) && Boolean(teamId) && !/FBCYL/i.test(collection ?? '') && dataSourceOf('scouting') === 'local'
  const { data } = useQuery<ReadonlySet<string>>({
    queryKey: ['left-players', collection, teamId],
    queryFn: async () => {
      try {
        const images = await loadWebImages(collection!, teamId)
        const today = new Date()
        return new Set(Object.entries(images.players).filter(([, extra]) => hasLeftTeam(extra, today)).map(([id]) => id))
      } catch {
        return NOBODY
      }
    },
    enabled,
    staleTime: 30 * 60_000,
  })
  return enabled && data ? data : NOBODY
}
