import type { LoggedAlert } from '../engine/types'
import { IndexedDbKeyedStore, memoryKeyedStore, safeKeyedStore, type KeyedStore } from './keyedStore'

/** Finished live matches kept on the device (issue #407), so the staff can review them later without the app being connected.
 *  What is kept is the package the match was followed with and the last merged FEB document (it has the whole play-by-play):
 *  the review replays it through the engine like the sample game. About 1 MB each, hence the limit. */
export interface FinishedMatch {
  /** FEB match code. */
  code: string
  /** "Local – Visitante". */
  title: string
  savedAt: string
  /** The competition of its package (readable, as the filters show it); absent in a match saved before issue #497. */
  competition?: string
  /** Id of the own team: the post-match report is built from its point of view (issue #409). */
  ownId: string
  /** Every alert the engine raised during the match, with the clock label it was shown at: the annex of the report (#409). */
  alerts: LoggedAlert[]
  /** The preparation package (decrypted JSON text) of the match. */
  plaintext: string
  /** The last merged FEB document (JSON text). */
  game: string
}

export type FinishedStore = KeyedStore<FinishedMatch>

/** About 1 MB each (the last document of a match), hence the limit. */
export const MAX_FINISHED = 5

export class IndexedDbFinishedStore extends IndexedDbKeyedStore<FinishedMatch> {
  constructor(name = 'basketlab-live-finished') { super(name, 'matches', MAX_FINISHED) }
}

export const memoryFinishedStore = (initial: FinishedMatch[] = []): FinishedStore => memoryKeyedStore(MAX_FINISHED, initial)

/** A store that never fails when IndexedDB is unavailable (private mode, tests): it lists nothing and forgets what it is given. */
export const safeFinishedStore = (inner: FinishedStore): FinishedStore => safeKeyedStore(inner)
