/** What the preview and the simulation read of a competition (issues #849, #850): its rows, its calendar and its gender, from the published files. The API has no predictive any more. */
import { fromSource } from '@/datasource/resolve'
import { localForecastInputs, type ForecastInputs } from '@/forecast/inputs'

export type { ForecastInputs } from '@/forecast/inputs'

export const getForecastInputs = (collection: string): Promise<ForecastInputs> =>
  fromSource('forecast', () => localForecastInputs(collection))
