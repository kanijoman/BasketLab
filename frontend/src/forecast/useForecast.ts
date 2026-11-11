// What the pages of the forecast read (#849, #850): the inputs of the competition (one query, kept ten minutes) and the model made from them once (the games, ratings, levels and the pool of
// scenarios), plus the list of its teams by name.
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getForecastInputs } from '@/api/forecast'
import type { Calendar } from '@/webdata/calendar'
import { buildGames } from './gameLog'
import { buildModel, type ForecastModel } from './pool'

export interface TeamOption { id: string; name: string }

export interface Forecast {
  model: ForecastModel | null
  calendar: Calendar | null
  teams: TeamOption[]
  isLoading: boolean
  error: unknown
}

export function useForecast(collection: string | undefined): Forecast {
  const { data, error, isLoading } = useQuery({
    queryKey: ['forecast-inputs', collection],
    queryFn: () => getForecastInputs(collection!),
    enabled: Boolean(collection),
    staleTime: 10 * 60_000,
    retry: false,
  })
  const model = useMemo(() => (data ? buildModel(buildGames(data.competition.team_rows, data.calendar), data.gender) : null), [data])
  const teams = useMemo(() => {
    const names = new Map<string, string>()
    for (const g of model?.games ?? []) { names.set(g.home, g.homeName); names.set(g.away, g.awayName) }
    for (const m of data?.calendar?.matches ?? []) { names.set(String(m.home.id), m.home.name); names.set(String(m.away.id), m.away.name) }
    return [...names].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name))
  }, [model, data])
  return { model, calendar: data?.calendar ?? null, teams, isLoading, error }
}
