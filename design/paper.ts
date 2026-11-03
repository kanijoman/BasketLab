/**
 * The colours of a PRINTED document (the PDFs the web makes, issues #714, #715): they are drawn on white paper whatever theme the screen is in, so they are the tones of the LIGHT
 * theme of tokens.css, not the ones of the theme in use. `designTokens.test.ts` keeps each one equal to its token, so the paper never drifts from the palette.
 */
export const PAPER = {
  ink: '#1f2328',            // --text
  muted: '#59636e',          // --text-muted
  line: '#d0d7de',           // --line
  surface: '#ffffff',        // --surface
  surfaceRaised: '#f0f3f6',  // --surface-raised
  ok: '#1a7f37',             // --ok
  bad: '#cf222e',            // --dev-bad
  own: '#0863cd',            // --sev-info: the team in a chart
  conceded: '#b45309',       // --pace-fast: what it concedes
  warn: '#9a6700',           // --warn
  faint: '#5d6670',          // --text-faint
  onData: '#ffffff',         // --on-data: ink over a bubble of data colour
  heatHot: '#ea580c',        // --chart-1: the hot layer of a heatmap
  heatCool: '#0969da',       // --chart-2: the cool layer
} as const

export type Tone = 'ink' | 'muted' | 'ok' | 'bad'
