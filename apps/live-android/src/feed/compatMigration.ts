/** What an update clears the first time it runs (issue #562): the matches kept on the device under an older ``REPLAY_COMPAT``.
 *
 *  A release that raises the compatibility changes what a replay says (the prior of the package, the calibration of the win probability): a list of kept matches
 *  that replay wrong is worse than an empty one. The first start under the new number removes them and says which; after that, whatever is kept is only warned
 *  about (``FinishedMatches``, ``RecordingsPanel``). A store that cannot be read leaves nothing marked, so the next start tries again. */
import type { FinishedStore } from './finishedStore'
import type { RecordingStore } from './recordingStore'
import { REPLAY_COMPAT, isStale } from './replayCompat'

export const COMPAT_KEY = 'basketlab-live-compat'

export interface Purged {
  finished: string[]
  recordings: string[]
}

export async function purgeStale(finished: FinishedStore, recordings: RecordingStore, storage: Storage = localStorage): Promise<Purged> {
  const none: Purged = { finished: [], recordings: [] }
  try {
    if (Number(storage.getItem(COMPAT_KEY) ?? 0) >= REPLAY_COMPAT) return none
    const old = { finished: (await finished.list()).filter(m => isStale(m.compat)), recordings: (await recordings.list()).filter(r => isStale(r.compat)) }
    for (const m of old.finished) await finished.remove(m.code)
    for (const r of old.recordings) await recordings.remove(r.code)
    storage.setItem(COMPAT_KEY, String(REPLAY_COMPAT))
    return { finished: old.finished.map(m => m.title), recordings: old.recordings.map(r => r.title) }
  } catch {
    return none
  }
}
