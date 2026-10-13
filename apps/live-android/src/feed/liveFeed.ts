/**
 * Live feed of a FEB match (issue #217): polls BoxScore + KeyFacts + ShotChart and hands the engine ONE merged
 * document per successful round (the same merge the recorder's replay uses). Built from what the first real
 * recording showed (docs/LIVE.md):
 *  - 404 before the match -> "waiting", polled once a minute (the recorder starts ~5 min before kick-off);
 *  - a 404 or a network error IN THE MIDDLE of the match (62 s on BoxScore, 11 s on KeyFacts) is a "gap": no
 *    update, the last state stays, polling continues every 10 s — never "not started" and never "finished";
 *  - one endpoint failing skips the whole round (an incomplete document would mislead the engine);
 *  - the final status (3) arrives ~15 minutes after the last play: keep polling a few more rounds, then stop.
 */
import type { Endpoint, FebClient } from './febClient'

export type FeedState =
  | { kind: 'idle' }
  | { kind: 'connecting' }
  | { kind: 'waiting' }
  | { kind: 'live'; lastOkAt: number }
  | { kind: 'gap'; lastOkAt: number | null; message?: string }
  | { kind: 'finished' }
  | { kind: 'stopped' }

export interface LiveFeedOptions {
  client: FebClient
  code: string
  /** Receives the merged document (JSON text); an exception is reported as a gap and does not stop the feed. */
  onDocument: (docJson: string) => void | Promise<void>
  onState: (state: FeedState) => void
  intervalMs?: number
  waitingIntervalMs?: number
  /** Extra rounds after the final status. */
  tailPolls?: number
  sleep?: (ms: number) => Promise<void>
  now?: () => number
}

const FINAL_STATUS = '3'

interface Round {
  /** Match status of the document that was delivered, when the round succeeded. */
  status: string | null
  failure?: string
  notStarted: boolean
}

export class LiveFeed {
  private stopped = false
  private readonly o: Required<LiveFeedOptions>

  constructor(options: LiveFeedOptions) {
    this.o = {
      intervalMs: 10_000, waitingIntervalMs: 60_000, tailPolls: 3,
      sleep: ms => new Promise(resolve => setTimeout(resolve, ms)), now: () => Date.now(), ...options,
    }
  }

  stop(): void {
    this.stopped = true
  }

  private async round(seenLive: boolean): Promise<Round> {
    const { client, code, onDocument } = this.o
    try {
      const box = await client.fetch(code, 'boxscore')
      if (box.status !== 200) {
        return { status: null, notStarted: box.status === 404 && !seenLive, failure: `FEB no responde (BoxScore ${box.status})` }
      }
      const [shots, facts] = await Promise.all((['shotchart', 'keyfacts'] as Endpoint[]).map(e => client.fetch(code, e)))
      if (shots.status !== 200 || facts.status !== 200) {
        const bad = shots.status !== 200 ? ['ShotChart', shots.status] : ['KeyFacts', facts.status]
        return { status: null, notStarted: false, failure: `FEB no responde (${bad[0]} ${bad[1]})` }
      }
      const header = (box.json as { HEADER?: { status?: unknown } }).HEADER
      const doc = {
        ...(box.json as object),
        PLAYBYPLAY: (facts.json as { PLAYBYPLAY?: unknown }).PLAYBYPLAY ?? {},
        SHOTCHART: (shots.json as { SHOTCHART?: unknown }).SHOTCHART ?? {},
      }
      await onDocument(JSON.stringify(doc))
      return { status: String(header?.status ?? ''), notStarted: false }
    } catch (error) {
      return { status: null, notStarted: false, failure: error instanceof Error ? error.message : String(error) }
    }
  }

  /** Runs until the match is over or ``stop()``; never rejects. */
  async start(): Promise<void> {
    const { onState, now } = this.o
    let lastOkAt: number | null = null
    let seenLive = false
    let tailLeft: number | null = null
    onState({ kind: 'connecting' })

    while (!this.stopped) {
      const round = await this.round(seenLive)
      if (this.stopped) break
      if (round.status !== null) {
        seenLive = true
        lastOkAt = now()
        onState({ kind: 'live', lastOkAt })
        if (round.status === FINAL_STATUS) {
          tailLeft = tailLeft === null ? this.o.tailPolls : tailLeft - 1
          if (tailLeft <= 0) {
            onState({ kind: 'finished' })
            return
          }
        }
      } else if (round.notStarted) {
        onState({ kind: 'waiting' })
      } else {
        onState({ kind: 'gap', lastOkAt, message: round.failure })
      }
      await this.o.sleep(round.notStarted ? this.o.waitingIntervalMs : this.o.intervalMs)
    }
    onState({ kind: 'stopped' })
  }
}
