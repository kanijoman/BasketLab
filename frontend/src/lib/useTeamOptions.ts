/** The {id, name} list of the teams of a collection, by name: ONE query for the pages that pick a team (issue #452). */
import { useQuery } from '@tanstack/react-query'
import { getTeamStats } from '@/api/client'
import type { TeamOption } from '@/components/PlayerSelect'

const EMPTY: TeamOption[] = []

/** ``onlyWithId`` drops the teams without ``team_id`` (otherwise the name stands in for it). */
export function useTeamOptions(collection: string | undefined, { onlyWithId = false } = {}): TeamOption[] {
  const { data } = useQuery<TeamOption[]>({
    queryKey: ['team-options', collection, onlyWithId],
    queryFn: () => getTeamStats(collection!).then(d =>
      (d.team_stats ?? [])
        .filter(t => !onlyWithId || t.team_id != null)
        .map(t => ({ id: String(t.team_id ?? t.team_name), name: t.team_name }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    ),
    enabled: Boolean(collection),
    staleTime: 10 * 60_000,
  })
  return data ?? EMPTY
}
