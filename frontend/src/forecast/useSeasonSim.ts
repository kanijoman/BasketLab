// The simulation of the league for a page (#850): it takes a few hundred milliseconds on a desktop and several times that on a phone, so it is made after the page has been drawn (the page shows a
// spinner meanwhile) and again only when the model or the calendar change.
import { useEffect, useState } from 'react'
import type { Calendar } from '@/webdata/calendar'
import type { ForecastModel } from './pool'
import { simulateSeason, type SeasonSim } from './seasonSim'

export function useSeasonSim(model: ForecastModel | null, calendar: Calendar | null): SeasonSim | null {
  const [done, setDone] = useState<{ model: ForecastModel; calendar: Calendar; sim: SeasonSim } | null>(null)
  useEffect(() => {
    if (!model || !calendar) return
    const timer = setTimeout(() => setDone({ model, calendar, sim: simulateSeason(model, calendar) }), 0)
    return () => clearTimeout(timer)
  }, [model, calendar])
  return done && done.model === model && done.calendar === calendar ? done.sim : null
}
