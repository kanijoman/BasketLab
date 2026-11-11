/**
 * The tones of the system (issue #190), shared by Badge and StatCard: accent (orange, the brand), secondary (blue), ok / warn / bad (good,
 * borderline and bad DATA, never the urgency of an alert) and neutral. Guide: docs/UI.md.
 */
export type Tone = 'neutral' | 'accent' | 'secondary' | 'ok' | 'warn' | 'bad'

/** A filled pill: a tint of the tone, its text and its border. The text of each tone is measured on its tint in both themes (`designTokens.test.ts`, #856). */
export const TONE_PILL: Record<Tone, string> = {
  neutral:   'bg-line/50 text-ink-muted',
  accent:    'bg-accent/20 text-accent-text border border-accent/30',
  secondary: 'bg-secondary/20 text-secondary-text border border-secondary/30',
  ok:        'bg-ok/15 text-ok-text border border-ok/30',
  warn:      'bg-warn/20 text-warn-text border border-warn/30',
  bad:       'bg-bad/20 text-bad-text border border-bad/30',
}

/** A panel that stands out: the border and a faint tint of the tone */
export const TONE_PANEL: Record<Tone, string> = {
  neutral:   'border-line',
  accent:    'border-accent/40 bg-accent/5',
  secondary: 'border-secondary/40 bg-secondary/5',
  ok:        'border-ok/40 bg-ok/5',
  warn:      'border-warn/40 bg-warn/5',
  bad:       'border-bad/40 bg-bad/5',
}
