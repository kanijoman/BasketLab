// The external sources of the data (ACB, FIBA, NCAA; #884) and which publication holds a competition. The collection of an external competition starts with the exact prefix of its source in capitals
// (`NCAA_D1_2026_SEC`), as `src/utils/collection_utils.source_of` reads it: nothing is asked to find out where it is, and a FEB or FBCYL competition that merely begins with the same letters is not one.
export const EXTERNAL_SOURCES = ['acb', 'euroleague', 'fiba', 'ncaa'] as const
export type ExternalSource = (typeof EXTERNAL_SOURCES)[number]

/** The external source a collection belongs to, or `null` (FEB, FBCYL and anything else). */
export function sourceOf(collection: string): ExternalSource | null {
  const prefix = collection.split('_', 1)[0]
  return EXTERNAL_SOURCES.find(source => source.toUpperCase() === prefix) ?? null
}
