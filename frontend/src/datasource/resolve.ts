// The ONE policy of the migration (issue #329), where it used to be copied in each reader: a dataset that is on reads the published files; if they cannot
// answer (`null`, `DataUnavailable`) it reads the API as before; an access problem (`ScopedAccessError`) is NOT «cannot answer» — the reader must unlock,
// the API is not a way round the keys —; any other error is an error, not something to hide behind the API.
import { dataSourceOf, type Dataset } from './switch'

/** The published data cannot answer this (down, unknown version, not published, damaged): the caller falls back to the API. */
export class DataUnavailable extends Error {}

export async function fromSource<T>(dataset: Dataset, local: () => Promise<T | null>, api: () => Promise<T>): Promise<T> {
  if (dataSourceOf(dataset) === 'local') {
    try {
      const answer = await local()
      if (answer !== null) return answer
    } catch (error) {
      if (!(error instanceof DataUnavailable)) throw error
    }
  }
  return api()
}
