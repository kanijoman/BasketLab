import type { AlertEntry } from './AlertList'
import type { Alert } from '../engine/types'

/** Time between two alerts of the same burst, so each one can be read (issue #375). */
export const ALERT_COOLDOWN_MS = 3000
/** Pending alerts beyond this many are grouped in one summary card, so a long burst does not lag behind the game. */
export const MAX_PENDING = 6

const RANK: Record<Alert['severity'], number> = { critical: 0, warning: 1, info: 2 }
const SUMMARY_TEXT_LIMIT = 70

interface Options {
  cooldownMs?: number
  maxPending?: number
  /** Nobody is reading while the app is in the background: what is pending is shown at once. */
  isHidden?: () => boolean
}

/**
 * Presents the alerts of the live feed one by one instead of in a block (issue #375).
 *
 * The first alert of a burst is shown at once and the next ones every 3 seconds, ordered by severity. Critical alerts do not
 * wait (and restart the clock); past 6 pending alerts the rest is grouped in one summary card. The engine has already
 * counted them all as seen: only the moment they appear changes. What is not paced (a jump in the timeline, a replay, a
 * loaded match) is shown at once, as before.
 */
export class AlertPacer {
  private pending: AlertEntry[] = []
  private lastShown = Number.NEGATIVE_INFINITY
  private timer: ReturnType<typeof setTimeout> | null = null
  private grouped = 0
  private readonly cooldownMs: number
  private readonly maxPending: number
  private readonly isHidden: () => boolean

  constructor(private readonly onShow: (items: AlertEntry[]) => void, options: Options = {}) {
    this.cooldownMs = options.cooldownMs ?? ALERT_COOLDOWN_MS
    this.maxPending = options.maxPending ?? MAX_PENDING
    this.isHidden = options.isHidden ?? (() => typeof document !== 'undefined' && document.visibilityState === 'hidden')
  }

  push(alerts: Alert[], at: string, paced: boolean): void {
    if (alerts.length === 0) return
    if (!paced || this.isHidden()) {
      this.show(alerts.map(alert => ({ alert, at })))
      return
    }
    const critical = alerts.filter(a => a.severity === 'critical')
    if (critical.length) {
      this.stop()                                    // the clock restarts: the pending timer was set for the old one
      this.show(critical.map(alert => ({ alert, at })))
    }
    const rest = alerts.filter(a => a.severity !== 'critical')
      .map((alert, order) => ({ alert, order }))
      .sort((x, y) => RANK[x.alert.severity] - RANK[y.alert.severity] || x.order - y.order)
    this.pending.push(...rest.map(({ alert }) => ({ alert, at })))
    this.group(at)
    this.schedule()
  }

  /** Shows everything pending now (the app went to the background). */
  flush(): void {
    this.stop()
    const items = this.pending
    this.pending = []
    this.grouped = 0
    items.forEach(item => this.show([item]))
  }

  /** Forgets what is pending, its timer and the cooldown (a new match, a restart). */
  clear(): void {
    this.stop()
    this.pending = []
    this.grouped = 0
    this.lastShown = Number.NEGATIVE_INFINITY
  }

  private show(items: AlertEntry[]): void {
    this.lastShown = Date.now()
    this.onShow(items)
  }

  private stop(): void {
    if (this.timer !== null) clearTimeout(this.timer)
    this.timer = null
  }

  /** Keeps at most ``maxPending`` alerts and turns the rest into one summary card at the end of the queue. */
  private group(at: string): void {
    const real = this.pending.filter(e => !e.alert.key.startsWith('summary:'))
    if (real.length <= this.maxPending) return
    const extra = real.slice(this.maxPending)
    const kept = real.slice(0, this.maxPending)
    this.grouped += extra.length
    const parts = extra.map(e => e.alert.message.length > SUMMARY_TEXT_LIMIT ? `${e.alert.message.slice(0, SUMMARY_TEXT_LIMIT)}…` : e.alert.message)
    const old = this.pending.find(e => e.alert.key.startsWith('summary:'))
    const earlier = typeof old?.alert.evidence.parts === 'object' ? (old!.alert.evidence.parts as string[]) : []
    const all = [...earlier, ...parts]
    const summary: Alert = {
      key: `summary:${this.grouped}`, id: 'resumen', severity: 'info', category: 'resumen',
      message: `+${this.grouped} avisos más: ${all.join(' · ')}`, evidence: { grouped: this.grouped, parts: all },
      proposal: [], rearm_s: null,
    }
    this.pending = [...kept, { alert: summary, at }]
  }

  private schedule(): void {
    if (this.timer !== null || this.pending.length === 0) return
    const wait = this.lastShown + this.cooldownMs - Date.now()
    if (wait <= 0) {
      this.release()
      return
    }
    this.timer = setTimeout(() => { this.timer = null; this.release() }, wait)
  }

  private release(): void {
    const next = this.pending.shift()
    if (!next) return
    if (next.alert.key.startsWith('summary:')) this.grouped = 0
    this.show([next])
    this.schedule()
  }
}
