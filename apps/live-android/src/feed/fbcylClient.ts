/**
 * Client of the FBCYL services the live mode reads (issue #446), the same addresses as the Python recorder (`src/live_prep/fbcyl_recorder.py`):
 *  - the calendar of a group (ESB API, Base64 JSON): the row of the match says its `adGameId` (the key of the live feed, only there when the match is about to start or was played),
 *    `state` (0 to play, 1 played) and its `universallyid` (the key of msstats, once the match has data);
 *  - the live feed of the web of the federation, `streaming/match-id/{adGameId}`: score, period, moves and the stats of every player, no token;
 *  - msstats, the definitive moves and stats once the match is over.
 * No service sends CORS headers either: on the tablet they go through Capacitor's native HTTP like FEB's (`defaultHttp`).
 */
import type { HttpGet } from './febClient'

const ESB = 'https://esb.optimalwayconsulting.com/fbcyl/1/jR4rgA5K6Chhh5vyfrxo9wTScdg2NT7K/FCBQWeb/getAllGamesByGrupWithMatchRecords'
const STREAMING = 'https://streaming.optimalwayconsulting.com/fbcyl/streaming/match-id'
const MSSTATS = 'https://msstats.optimalwayconsulting.com/v1/fbcyl'

export const calendarUrl = (group: string) => `${ESB}/${group}/0`
export const streamUrl = (adGameId: string) => `${STREAMING}/${adGameId}`
export const movesUrl = (uuid: string) => `${MSSTATS}/getJsonWithMatchMoves/${uuid}`
export const statsUrl = (uuid: string) => `${MSSTATS}/getJsonWithMatchStats/${uuid}?currentSeason=true`

/** What the app reads of a row of the calendar of a group. */
export interface CalendarRow {
  idMatch: string
  round: string
  state: string
  isLive: boolean
  /** The key of the live feed: null until the match is about to start. */
  adGameId: string | null
  /** The key of msstats: null until the match has data. */
  universallyid: string | null
  matchStartedHour: string | null
}

interface RawRow { idMatch?: unknown; state?: unknown; isLive?: unknown; adGameId?: unknown; universallyid?: unknown; matchStartedHour?: unknown }

const text = (value: unknown): string | null => (value === null || value === undefined || String(value).trim() === '' ? null : String(value))

/** The rows of the answer of the calendar (Base64 of UTF-8 JSON), each with its round; empty when the answer is not a good one. */
export function decodeCalendar(answer: string): CalendarRow[] {
  try {
    const bytes = Uint8Array.from(atob(answer.trim()), ch => ch.charCodeAt(0))
    const data = JSON.parse(new TextDecoder('utf-8').decode(bytes)) as { result?: string; messageData?: { rounds?: Record<string, { matches?: Record<string, RawRow> }> } }
    if (data.result !== 'OK') return []
    return Object.entries(data.messageData?.rounds ?? {}).flatMap(([round, r]) => Object.values(r.matches ?? {}).map((m): CalendarRow => ({
      idMatch: String(m.idMatch), round, state: String(m.state ?? ''), isLive: m.isLive === true, adGameId: text(m.adGameId), universallyid: text(m.universallyid),
      matchStartedHour: text(m.matchStartedHour),
    })))
  } catch {
    return []
  }
}

export class FbcylClient {
  constructor(private readonly http: HttpGet) {}

  /** The calendar of a group; it throws when it cannot be read (the feed says so and goes on asking, it never takes an empty calendar for a good one). */
  async calendar(group: string): Promise<CalendarRow[]> {
    const answer = await this.http(calendarUrl(group))
    if (answer.status !== 200) throw new Error(`calendario ${answer.status}`)
    const rows = decodeCalendar(answer.text)
    if (rows.length === 0) throw new Error('calendario vacío')
    return rows
  }

  /** The live feed of a match: its body as text (the engine reads it), or null when the service does not answer well. */
  async stream(adGameId: string): Promise<{ status: number; text: string | null }> {
    const answer = await this.http(streamUrl(adGameId))
    return { status: answer.status, text: answer.status === 200 ? answer.text : null }
  }

  /** The definitive moves and stats of a match that is over, or null while msstats does not have them (it is published a little after the end). */
  async final(uuid: string): Promise<{ moves: string; stats: string } | null> {
    const [moves, stats] = await Promise.all([this.http(movesUrl(uuid)), this.http(statsUrl(uuid))])
    return moves.status === 200 && stats.status === 200 ? { moves: moves.text, stats: stats.text } : null
  }
}
