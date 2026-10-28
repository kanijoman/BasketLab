/**
 * Tailwind preset over design/tokens.css (issues #228, #188): the vocabulary of the web (frontend/tailwind.config.js uses it).
 *
 * Colors use the `--x-rgb` channels where a tint makes sense, so `bg-surface/50` and `bg-accent/20` work; every name changes with the theme.
 *   canvas (page) · surface (cards) · surface-raised (hover, inputs) · line (borders)
 *   ink (text) · ink-muted (secondary text) · ink-faint (hints, placeholders)
 *   accent (orange: actions, selection) · accent-text (orange text) · accent-solid / accent-hover (filled buttons, with accent-ink on them)
 *   secondary (blue: the other league, links) · focus (focus ring)
 *   ok / bad / warn (good, bad and borderline DATA; never for alerts: sev-*) · q1..q4 (quartiles) · chart-1..8 (series)
 */
const channel = (name) => `rgb(var(--${name}-rgb) / <alpha-value>)`

module.exports = {
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        canvas: channel('bg'),
        surface: { DEFAULT: channel('surface'), raised: channel('surface-raised') },
        line: channel('line'),
        ink: { DEFAULT: channel('text'), muted: channel('text-muted'), faint: channel('text-faint') },
        accent: {
          DEFAULT: channel('accent'), ink: 'var(--accent-ink)', text: channel('accent-text'),
          solid: 'var(--accent-solid)', hover: 'var(--accent-hover)',
        },
        secondary: { DEFAULT: channel('secondary'), text: channel('secondary-text'), solid: 'var(--secondary-solid)', hover: 'var(--secondary-hover)' },
        focus: channel('focus'),
        ok: channel('ok'),
        bad: channel('bad'),
        warn: channel('warn'),
        sev: { critical: channel('sev-critical'), warning: channel('sev-warning'), info: channel('sev-info') },
        cat: {
          faltas: 'var(--cat-faltas)', rotacion: 'var(--cat-rotacion)', rival: 'var(--cat-rival)',
          juego: 'var(--cat-juego)', ritmo: 'var(--cat-ritmo)',
        },
        q1: { bg: 'var(--q1-bg)', text: 'var(--q1-text)' },
        q2: { bg: 'var(--q2-bg)', text: 'var(--q2-text)' },
        q3: { bg: 'var(--q3-bg)', text: 'var(--q3-text)' },
        q4: { bg: 'var(--q4-bg)', text: 'var(--q4-text)' },
        chart: Object.fromEntries([1, 2, 3, 4, 5, 6, 7, 8].map(i => [i, `var(--chart-${i})`])),
      },
      boxShadow: { card: 'var(--shadow-card)', panel: 'var(--shadow-panel)', glow: 'var(--shadow-glow)' },
      spacing: { touch: 'var(--touch)' },
      fontFamily: { sans: ['var(--font-sans)'], mono: ['var(--font-mono)'], display: ['var(--font-display)'] },
    },
  },
}
