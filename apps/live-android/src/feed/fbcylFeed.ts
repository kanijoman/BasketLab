/**
 * Live feed of a FBCYL match (issue #446): the same loop as FEB's (`FeedLoop`), another source.
 *
 * The match is in the calendar of its group from the start, but its `adGameId` (the key of the live feed) only exists when it is about to start: until then the feed waits asking the
 * calendar once a minute. Once it has it, it asks the stream every 10 s and hands the body to the engine as it is (`onStream`: the engine converts it and ignores the readings that go
 * backwards, which the real service answers at the end of a match). The calendar is big, so while the match is on it is read only every `calendarEveryMs`, to see when it is played: then the
 * definitive moves and stats of msstats close the match (`onFinal`) and the feed finishes. msstats is published a little after the end: until it answers, the stream goes on.
 */
import type { FbcylClient } from './fbcylClient'
import type { LagInfo } from './feedLag'
import { FeedLoop, type FeedLoopOptions, type Round } from './feedLoop'

export interface FbcylFeedOptions extends FeedLoopOptions {
  client: FbcylClient
  /** `idMatch` of the match in the calendar. */
  matchId: string
  /** The group of the match in the calendar of the federation. */
  groupId: string
  /** Receives the body of every reading of the stream (JSON text); an exception is reported as a gap and does not stop the feed. */
  onStream: (body: string, info: LagInfo) => void | Promise<void>
  /** Receives the definitive moves and stats (JSON text) once the match is over. */
  onFinal: (moves: string, stats: string) => void | Promise<void>
  /** An answer of the stream was not good in the middle of the match (the recording keeps the gap). */
  onFailure?: (endpoint: 'stream') => void
  /** How often the calendar is read while the match is on, to see whether it is over. */
  calendarEveryMs?: number
}

export class FbcylFeed extends FeedLoop {
  private readonly source: FbcylFeedOptions
  private adGameId: string | null = null
  private calendarAt: number | null = null
  private closed = false

  constructor(options: FbcylFeedOptions) {
    super({ ...options, tailPolls: 0 })              // msstats is the end: nothing more to ask after closing the match
    this.source = options
  }

  protected async round(seenLive: boolean): Promise<Round> {
    const { client, onStream, onFailure } = this.source
    if (this.closed) return { live: true, final: true, notStarted: false }
    try {
      const seen = await this.readCalendar()
      if (seen.notStarted || seen.failure) return { live: false, notStarted: !!seen.notStarted, failure: seen.failure }
      if (seen.over) {
        const closing = await this.close(seen.over)
        if (closing) return closing
      }
      if (this.stopped || this.adGameId === null) return { live: false, notStarted: false }
      const reading = await client.stream(this.adGameId)
      if (reading.text === null) {
        if (seenLive) onFailure?.('stream')
        return { live: false, notStarted: false, failure: `FBCYL no responde (directo ${reading.status})` }
      }
      if (this.stopped) return { live: false, notStarted: false }
      await onStream(reading.text, { receivedAt: this.loop.now(), ageS: null, lines: [] })       // FBCYL says neither the age of its cache nor when each move was logged: no delay is measured
      return { live: true, notStarted: false }
    } catch (error) {
      if (seenLive) this.source.onFailure?.('stream')
      return { live: false, notStarted: false, failure: `FBCYL no responde (${error instanceof Error ? error.message : String(error)})` }
    }
  }

  /** The calendar, when it is time: waiting for the `adGameId` it is read every round; once the match is on, every `calendarEveryMs`. */
  private async readCalendar(): Promise<{ notStarted?: boolean; failure?: string; over?: string }> {
    const { client, matchId, groupId, calendarEveryMs = 60_000 } = this.source
    const now = this.loop.now()
    if (this.adGameId !== null && this.calendarAt !== null && now - this.calendarAt < calendarEveryMs) return {}
    const rows = await client.calendar(groupId)
    this.calendarAt = now
    const row = rows.find(r => r.idMatch === matchId)
    if (!row) return { failure: 'FBCYL no responde: el partido no está en el calendario' }
    if (row.adGameId !== null) this.adGameId = row.adGameId
    if (this.adGameId === null) return { notStarted: true }
    return row.state === '1' && row.universallyid !== null ? { over: row.universallyid } : {}
  }

  /** The match is over: close it with msstats. null while msstats has nothing yet (the stream goes on and the next calendar reading tries again). */
  private async close(uuid: string): Promise<Round | null> {
    const final = await this.source.client.final(uuid)
    if (final === null) {
      this.calendarAt = null                       // read the calendar again next round: it is the moment msstats appears
      return null
    }
    if (this.stopped) return { live: false, notStarted: false }
    await this.source.onFinal(final.moves, final.stats)
    this.closed = true
    return { live: true, final: true, notStarted: false }
  }
}
