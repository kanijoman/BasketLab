/**
 * Tailwind preset over design/tokens.css (issue #228), ready for the web (#188, U0).
 *
 *   // frontend/tailwind.config.js
 *   module.exports = { presets: [require('../design/tailwind-preset.cjs')], content: [...] }
 *
 * Colors use the `--x-rgb` channels so `bg-surface/50` and `text-accent/80` work.
 */
const channel = (name) => `rgb(var(--${name}-rgb) / <alpha-value>)`

module.exports = {
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: channel('bg'),
        surface: { DEFAULT: channel('surface'), raised: 'var(--surface-raised)' },
        line: channel('line'),
        ink: { DEFAULT: channel('text'), muted: 'var(--text-muted)' },
        accent: { DEFAULT: channel('accent'), ink: 'var(--accent-ink)' },
        ok: 'var(--ok)',
        sev: { critical: channel('sev-critical'), warning: channel('sev-warning'), info: channel('sev-info') },
        cat: {
          faltas: 'var(--cat-faltas)', rotacion: 'var(--cat-rotacion)', rival: 'var(--cat-rival)',
          juego: 'var(--cat-juego)', ritmo: 'var(--cat-ritmo)',
        },
      },
      borderRadius: { sm: 'var(--radius-sm)', md: 'var(--radius-md)', lg: 'var(--radius-lg)' },
      spacing: { touch: 'var(--touch)' },
      fontFamily: { sans: ['var(--font-sans)'], mono: ['var(--font-mono)'] },
    },
  },
}
