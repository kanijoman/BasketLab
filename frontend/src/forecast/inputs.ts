// What the forecast reads of a competition (#849, #850): its rows (the games, from `web-data`), its calendar (it may have none published) and its gender (it may not say it). Only the published
// files: the API has no predictive any more.
import { loadCompetition } from '@/localdata/source'
import type { Competition } from '@/localdata/competition'
import { loadWebCollectionInfos, WebDataUnavailable } from '@/webdata/client'
import { loadWebCalendar, type Calendar } from '@/webdata/calendar'

export interface ForecastInputs {
  collection: string
  competition: Competition
  /** `null` when the competition has no calendar published: the preview still works from the rows, the simulation of the league does not. */
  calendar: Calendar | null
  gender?: 'F' | 'M'
}

async function orNothing<T>(read: () => Promise<T>): Promise<T | undefined> {
  try {
    return await read()
  } catch (error) {
    if (error instanceof WebDataUnavailable) return undefined
    throw error
  }
}

/** The inputs of a competition, or `null` when its rows are not published. */
export async function localForecastInputs(collection: string): Promise<ForecastInputs | null> {
  const competition = await loadCompetition(collection)
  if (!competition) return null
  const [calendar, infos] = await Promise.all([orNothing(() => loadWebCalendar(collection)), orNothing(loadWebCollectionInfos)])
  return { collection, competition, calendar: calendar ?? null, gender: infos?.find(i => i.collection === collection)?.gender }
}
