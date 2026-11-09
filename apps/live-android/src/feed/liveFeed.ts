/**
 * Live feed of a FEB match (issue #217): polls BoxScore + KeyFacts + ShotChart and hands the engine ONE merged
 * document per successful round (the same merge the recorder's replay uses). The loop (states, waits, stop, poke, tail) is `FeedLoop`, shared with the FBCYL feed. Built from what the first real
 * recording showed (docs/LIVE.md):
 *  - 404 before the match -> "waiting", polled once a minute (the recorder starts ~5 min before kick-off);
 *  - a 404 or a network error IN THE MIDDLE of the match (62 s on BoxScore, 11 s on KeyFacts) is a "gap": no
 *    update, the last state stays, polling continues every 10 s — never "not started" and never "finished";
 *  - one endpoint failing skips the whole round (an incomplete document would mislead the engine);
 *  - the final status (3) arrives ~15 minutes after the last play: keep polling a few more rounds, then stop.
 */
import type { Endpoint, FebClient } from './febClient'
import type { LagInfo } from './feedLag'
import { FeedLoop, type FeedLoopOptions, type Round } from './feedLoop'

export type { FeedState } from './feedLoop'

export interface LiveFeedOptions extends Omit<FeedLoopOptions, 'onState'> {
  client: FebClient
  code: string
  /** Receives the merged document (JSON text); an exception is reported as a gap and does not stop the feed. */
  onDocument: (docJson: string, info: LagInfo) => void | Promise<void>
  onState: FeedLoopOptions['onState']
  /** An endpoint failed in the middle of the match (issue #416): the recording keeps the gap. Network errors count as the box score. */
  onFailure?: (endpoint: Endpoint) => void
}

const FINAL_STATUS = '3'

/** What the delay meter needs of a document (issue #411): when it arrived, the oldest cache age FEB announced and when each line was logged. */
function lagInfo(receivedAt: number, ages: (number | undefined)[], playByPlay: unknown): LagInfo {
  const known = ages.filter((a): a is number => a !== undefined)
  const lines = ((playByPlay as { LINES?: { num?: unknown; LogTimeUtc?: unknown }[] } | undefined)?.LINES ?? [])
  return {
    receivedAt, ageS: known.length ? Math.max(...known) : null,
    lines: lines.map(l => ({ num: String(l.num), logUtc: typeof l.LogTimeUtc === 'string' ? l.LogTimeUtc : null })),
  }
}

export class LiveFeed extends FeedLoop {
  private readonly source: LiveFeedOptions
  private readonly onFailure: (endpoint: Endpoint) => void

  constructor(options: LiveFeedOptions) {
    super(options)
    this.source = options
    this.onFailure = options.onFailure ?? (() => undefined)
  }

  /** One round of FEB: the three endpoints, merged into one document for the engine. */
  protected async round(seenLive: boolean): Promise<Round> {
    const { client, code, onDocument } = this.source
    try {
      const box = await client.fetch(code, 'boxscore')
      if (box.status !== 200) {
        if (seenLive) this.onFailure('boxscore')
        return { live: false, notStarted: box.status === 404 && !seenLive, failure: `FEB no responde (BoxScore ${box.status})` }
      }
      const [shots, facts] = await Promise.all((['shotchart', 'keyfacts'] as Endpoint[]).map(e => client.fetch(code, e)))
      if (shots.status !== 200 || facts.status !== 200) {
        const bad = shots.status !== 200 ? ['ShotChart', shots.status] : ['KeyFacts', facts.status]
        this.onFailure(shots.status !== 200 ? 'shotchart' : 'keyfacts')
        return { live: false, notStarted: false, failure: `FEB no responde (${bad[0]} ${bad[1]})` }
      }
      const header = (box.json as { HEADER?: { status?: unknown } }).HEADER
      const doc = {
        ...(box.json as object),
        PLAYBYPLAY: (facts.json as { PLAYBYPLAY?: unknown }).PLAYBYPLAY ?? {},
        SHOTCHART: (shots.json as { SHOTCHART?: unknown }).SHOTCHART ?? {},
      }
      if (this.stopped) return { live: false, notStarted: false } // stopped while FEB was answering
      await onDocument(JSON.stringify(doc), lagInfo(this.loop.now(), [box.age, shots.age, facts.age], doc.PLAYBYPLAY))
      return { live: true, final: String(header?.status ?? '') === FINAL_STATUS, notStarted: false }
    } catch (error) {
      if (seenLive) this.onFailure('boxscore')
      return { live: false, notStarted: false, failure: error instanceof Error ? error.message : String(error) }
    }
  }
}
