/**
 * The loop every live feed runs (issues #217, #446): ask the source, report what the connection is doing and wait for the next round. FEB's feed (`LiveFeed`) and FBCYL's (`FbcylFeed`)
 * differ in WHAT a round asks and in how the match is told to be over; the rest (states, the wait between rounds, stopping, poking the loop when the app comes back to the foreground,
 * the few rounds after the end) is written once here so both leagues behave the same:
 *  - before the match: "waiting", asked once a minute;
 *  - a failed round in the middle of the match is a "gap": no update, the last state stays, asked again every 10 s — never "not started" and never "finished";
 *  - after the end a few more rounds (`tailPolls`) and then "finished".
 */

export type FeedState =
  | { kind: 'idle' }
  | { kind: 'connecting' }
  | { kind: 'waiting' }
  | { kind: 'live'; lastOkAt: number }
  | { kind: 'gap'; lastOkAt: number | null; message?: string }
  | { kind: 'finished' }
  | { kind: 'stopped' }  // set by the UI when the user disconnects (a stopped feed reports nothing)

export interface FeedLoopOptions {
  onState: (state: FeedState) => void
  intervalMs?: number
  waitingIntervalMs?: number
  /** Extra rounds after the end of the match. */
  tailPolls?: number
  sleep?: (ms: number) => Promise<void>
  now?: () => number
}

/** What one round found. */
export interface Round {
  /** Data arrived: the match is on. */
  live: boolean
  /** The match is over (the loop asks `tailPolls` more times and finishes). */
  final?: boolean
  /** Nothing to see yet because the match has not started (waiting, asked at the slow pace). */
  notStarted: boolean
  failure?: string
}

export abstract class FeedLoop {
  protected stopped = false
  /** Ends the current wait between rounds (set only while the loop is waiting). */
  private wake: (() => void) | null = null
  protected readonly loop: Required<FeedLoopOptions>

  protected constructor(options: FeedLoopOptions) {
    this.loop = { intervalMs: 10_000, waitingIntervalMs: 60_000, tailPolls: 3, sleep: ms => new Promise(resolve => setTimeout(resolve, ms)), now: () => Date.now(), ...options }
  }

  /** One round: ask the source and hand over what arrived. Never rejects. */
  protected abstract round(seenLive: boolean): Promise<Round>

  stop(): void {
    this.stopped = true
    this.poke()
  }

  /** Polls now instead of waiting out the rest of the sleep (issue #220: the app is back in the foreground or the network is back, and the WebView had frozen its timers).
   *  It does nothing while a round is running: that one is already asking. */
  poke(): void {
    this.wake?.()
  }

  private wait(ms: number): Promise<void> {
    return new Promise<void>(resolve => {
      this.wake = () => { this.wake = null; resolve() }
      void this.loop.sleep(ms).then(() => this.wake?.())
    })
  }

  /** Reports a state unless the feed was stopped: after ``stop()`` nothing is reported any more (the UI may be gone). */
  protected report(state: FeedState): void {
    if (!this.stopped) this.loop.onState(state)
  }

  /** Runs until the match is over or ``stop()`` (then it is silent: no state, no document); never rejects. */
  async start(): Promise<void> {
    let lastOkAt: number | null = null
    let seenLive = false
    let tailLeft: number | null = null
    this.report({ kind: 'connecting' })

    while (!this.stopped) {
      const round = await this.round(seenLive)
      if (this.stopped) break
      if (round.live) {
        seenLive = true
        lastOkAt = this.loop.now()
        this.report({ kind: 'live', lastOkAt })
        if (round.final) {
          tailLeft = tailLeft === null ? this.loop.tailPolls : tailLeft - 1
          if (tailLeft <= 0) {
            this.report({ kind: 'finished' })
            return
          }
        }
      } else if (round.notStarted) {
        this.report({ kind: 'waiting' })
      } else {
        this.report({ kind: 'gap', lastOkAt, message: round.failure })
      }
      await this.wait(round.notStarted ? this.loop.waitingIntervalMs : this.loop.intervalMs)
    }
  }
}
