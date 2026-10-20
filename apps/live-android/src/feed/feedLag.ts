/** How late the live feed of FEB is, measured on the device (issue #411).
 *
 *  Each line of the play-by-play carries ``LogTimeUtc``, the moment the table logged it. The delay of a line is the time between that and the poll
 *  that first saw it: it adds up what FEB takes to publish it, the age of its cache (FEB answers ``cache-control: public,max-age=15`` and the
 *  header ``age`` says how old the answer is) and the wait for our next poll. Measured on two real matches: median ~40 s, p95 ~60 s, of which
 *  the cache is ~11 s and the poll ~5 s on average: polling faster could win a couple of seconds at most (docs/evaluaciones/2026-10-20_retraso-del-feed.md).
 */

export interface LagLine {
  num: string
  /** "2026-10-17 19:12:40" (UTC) or null when FEB did not say. */
  logUtc: string | null
}

export interface LagInfo {
  /** Device time (ms) at which the poll got the document. */
  receivedAt: number
  /** Largest ``age`` header of the three answers of the poll (seconds), if FEB sent it. */
  ageS: number | null
  lines: LagLine[]
}

export interface LagSummary {
  /** Lines measured. */
  samples: number
  medianS: number
  p90S: number
  maxS: number
  /** Median of the ``age`` headers (the cache of FEB), null if they were not seen. */
  ageMedianS: number | null
  polls: number
  /** Polls that brought at least one new line (the first one, the catch-up, does not count). */
  pollsWithNews: number
  /** The clock of the device is behind FEB's: the measured delays are negative, so they say nothing. */
  skewed: boolean
}

/** Samples needed before the connection panel says a number. */
export const MIN_SAMPLES = 5

const LOG_TIME = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/

function logMillis(logUtc: string | null): number | null {
  const m = logUtc ? LOG_TIME.exec(logUtc) : null
  return m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) : null
}

function percentile(sorted: number[], p: number): number {
  return sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))]
}

export class FeedLagMeter {
  private readonly seen = new Set<string>()
  private readonly lags: number[] = []
  private readonly ages: number[] = []
  private polls = 0
  private pollsWithNews = 0

  /** One document of the feed. The first one is the catch-up of a match already on: its lines are not measured. */
  observe(info: LagInfo): void {
    const first = this.polls === 0
    this.polls += 1
    if (info.ageS !== null) this.ages.push(info.ageS)
    let news = false
    for (const line of info.lines) {
      if (this.seen.has(line.num)) continue
      this.seen.add(line.num)
      news = true
      const logged = logMillis(line.logUtc)
      if (!first && logged !== null) this.lags.push((info.receivedAt - logged) / 1000)
    }
    if (news && !first) this.pollsWithNews += 1
  }

  summary(): LagSummary | null {
    if (this.polls === 0) return null
    const lags = [...this.lags].sort((a, b) => a - b)
    const ages = [...this.ages].sort((a, b) => a - b)
    const median = lags.length ? percentile(lags, 0.5) : 0
    return {
      samples: lags.length, medianS: median, p90S: lags.length ? percentile(lags, 0.9) : 0, maxS: lags.length ? lags[lags.length - 1] : 0,
      ageMedianS: ages.length ? percentile(ages, 0.5) : null, polls: this.polls, pollsWithNews: this.pollsWithNews,
      skewed: lags.length >= MIN_SAMPLES && median < 0,
    }
  }
}

/** The line of the connection panel: how late FEB's data is. Null while there are too few samples to say. */
export function lagText(s: LagSummary): string | null {
  if (s.skewed) return 'El reloj de la tablet no está en hora: no se puede medir el retraso de FEB.'
  if (s.samples < MIN_SAMPLES) return null
  return `Datos de FEB con unos ${Math.round(s.medianS)} s de retraso (el 90 % llega en menos de ${Math.round(s.p90S)} s).`
}

/** The note of the session log when the connection ends: the three facts that decide how often to ask FEB. */
export function lagNote(s: LagSummary): string {
  const news = s.polls > 1 ? `${Math.round((100 * s.pollsWithNews) / (s.polls - 1))} % de los sondeos traen novedades` : 'sin sondeos suficientes'
  const age = s.ageMedianS === null ? 'caché de FEB: sin dato' : `caché de FEB: ${Math.round(s.ageMedianS)} s de mediana`
  const lines = s.samples > 0
    ? `mediana ${Math.round(s.medianS)} s, p90 ${Math.round(s.p90S)} s, máx. ${Math.round(s.maxS)} s (${s.samples} líneas)`
    : 'sin líneas medidas'
  return `Retraso de los datos de FEB: ${lines}; ${age}; ${news}`
}
