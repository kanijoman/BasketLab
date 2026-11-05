// The ONE policy of the migration (issues #329, #334): a dataset that is local reads the published files and NOTHING asks a server in its place. If the files cannot answer
// (`null`, `DataUnavailable`) the reader gets a clear error — `DataNotAvailable`, or the error of the files, which already says why — or, if the caller has one, a neutral value
// (`whenUnavailable`: «nothing published» is an empty list, not a failure). An access problem (`ScopedAccessError`) is NOT «cannot answer»: the reader must unlock. The API is only read
// when it is asked for on purpose (`?data=api`, see `switch.ts`: the mode of the development and of the e2e).
import { dataSourceOf, type Dataset } from './switch'

/** The published data cannot answer this (down, unknown version, not published, damaged). */
export class DataUnavailable extends Error {}

/** The published files cannot answer this question and nothing else is asked: the message is for the reader. */
export class DataNotAvailable extends DataUnavailable {
  constructor(readonly dataset: Dataset) {
    super('Estos datos no están disponibles todavía para esta competición o no se pueden calcular sin servidor. Prueba con otra competición o vuelve más tarde.')
  }
}

export async function fromSource<T>(dataset: Dataset, local: () => Promise<T | null>, api: () => Promise<T>, whenUnavailable?: () => T): Promise<T> {
  if (dataSourceOf(dataset) !== 'local') return api()
  let failure: DataUnavailable = new DataNotAvailable(dataset)
  try {
    const answer = await local()
    if (answer !== null) return answer
  } catch (error) {
    if (!(error instanceof DataUnavailable)) throw error
    failure = error
  }
  if (whenUnavailable) return whenUnavailable()
  throw failure
}
