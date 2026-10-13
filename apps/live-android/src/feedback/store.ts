/**
 * What the staff did with each alert (issue #235): followed, dismissed or already done. Kept on the device per
 * match and exportable as JSON, so the rule evaluator can measure obedience and not only coincidence.
 * Times are ISO strings (real clock) so they can be joined with the feed's LogTimeUtc.
 */
import type { Alert } from '../engine/types'

export type Verdict = 'seguida' | 'descartada' | 'ya_hecho'

export interface FeedbackRecord {
  key: string
  id: string
  severity: string
  category: string
  /** Game-seconds since tip-off when the alert was shown. */
  elapsed: number
  shown_at: string
  verdict: Verdict | null
  decided_at: string | null
}

export interface FeedbackExport {
  v: 1
  kind: 'basketlab-live-feedback'
  exported_at: string
  context: string
  package_id: string | null
  entries: FeedbackRecord[]
}

/** The part of the Web Storage API the store needs (injected in tests). */
export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

const PREFIX = 'basketlab-live-feedback:'

export function defaultStorage(): StorageLike | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null  // blocked storage (private window, restricted WebView)
  }
}

export function feedbackFileName(context: string, exportedAt: string): string {
  return `feedback-${context.replace(/[^A-Za-z0-9]+/g, '-')}-${exportedAt.slice(0, 10)}.json`
}

export class FeedbackStore {
  private readonly items = new Map<string, FeedbackRecord>()

  constructor(
    readonly context: string,
    private readonly packageId: string | null = null,
    private readonly storage: StorageLike | null = defaultStorage(),
  ) {
    for (const r of this.read()) this.items.set(r.key, r)
  }

  /** Remembers an alert the moment it is shown; a key already known keeps its first record. */
  register(alert: Alert, elapsed: number, shownAt: string): FeedbackRecord {
    const known = this.items.get(alert.key)
    if (known) return known
    const record: FeedbackRecord = {
      key: alert.key, id: alert.id, severity: alert.severity, category: alert.category,
      elapsed, shown_at: shownAt, verdict: null, decided_at: null,
    }
    this.items.set(record.key, record)
    this.write()
    return record
  }

  setVerdict(key: string, verdict: Verdict | null, decidedAt: string): void {
    const record = this.items.get(key)
    if (!record) return
    this.items.set(key, { ...record, verdict, decided_at: verdict ? decidedAt : null })
    this.write()
  }

  get(key: string): FeedbackRecord | undefined {
    return this.items.get(key)
  }

  /** In the order the alerts were shown. */
  records(): FeedbackRecord[] {
    return [...this.items.values()]
  }

  clear(): void {
    this.items.clear()
    try {
      this.storage?.removeItem(PREFIX + this.context)
    } catch {
      /* nothing to clear */
    }
  }

  export(exportedAt: string): FeedbackExport {
    return {
      v: 1, kind: 'basketlab-live-feedback', exported_at: exportedAt,
      context: this.context, package_id: this.packageId, entries: this.records(),
    }
  }

  private read(): FeedbackRecord[] {
    try {
      const parsed: unknown = JSON.parse(this.storage?.getItem(PREFIX + this.context) ?? '[]')
      return Array.isArray(parsed) ? (parsed as FeedbackRecord[]).filter(r => r && typeof r.key === 'string') : []
    } catch {
      return []  // missing, corrupt or unreadable: start empty
    }
  }

  private write(): void {
    try {
      this.storage?.setItem(PREFIX + this.context, JSON.stringify(this.records()))
    } catch {
      /* storage full or unavailable: the history lives on in memory for this session */
    }
  }
}
