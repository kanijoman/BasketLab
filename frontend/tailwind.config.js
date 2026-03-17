/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // ── Surface palette ─────────────────────────────────────────────
        surface: {
          base:   '#0D1117',   // page background
          raised: '#161B22',   // cards, panels
          border: '#30363D',   // borders, dividers
          hover:  '#1C2128',   // hover state
        },
        // ── Brand accent — court green ───────────────────────────────────
        brand: {
          50:   '#f0fdf4',
          100:  '#dcfce7',
          200:  '#bbf7d0',
          400:  '#4ade80',
          500:  '#22C55E',
          600:  '#16a34a',
          700:  '#15803d',
          800:  '#166534',
          900:  '#14532d',
        },
        // ── Secondary accent — analytics blue ───────────────────────────
        accent: {
          400:  '#60a5fa',
          500:  '#3B82F6',
          600:  '#2563eb',
          700:  '#1d4ed8',
        },
        // ── Semantic feedback ────────────────────────────────────────────
        up:     '#22C55E',   // trend up / positive
        down:   '#EF4444',   // trend down / negative
        warn:   '#F59E0B',   // warning / neutral trend
        // ── Text hierarchy ───────────────────────────────────────────────
        ink: {
          primary:   '#E6EDF3',
          secondary: '#8B949E',
          muted:     '#484F58',
        },
        // ── Quartile coloring: use saturated dark colors with enough contrast on #161B22 ──────
        q1: { bg: '#0f3d1e', text: '#4ade80' },  // best  (dark green  → bright green text)
        q2: { bg: '#1e3510', text: '#86efac' },  // above median
        q3: { bg: '#3d2c0a', text: '#fcd34d' },  // below median
        q4: { bg: '#3d1010', text: '#f87171' },  // worst (dark red   → bright red text)
        // ── Legacy aliases (keep existing pages compiling) ───────────────
        primary: {
          50:  '#f0fdf4',
          500: '#22C55E',
          600: '#16a34a',
          700: '#15803d',
        },
        court: {
          950: '#0D1117',
          900: '#161B22',
          800: '#1C2128',
        },
      },
      fontFamily: {
        sans: ['Inter var', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '0.5rem',
        card:    '0.75rem',
        pill:    '9999px',
      },
      boxShadow: {
        card:  '0 1px 3px rgba(0,0,0,.4), 0 1px 2px rgba(0,0,0,.3)',
        panel: '0 4px 24px rgba(0,0,0,.5)',
        glow:  '0 0 12px rgba(34,197,94,.25)',
      },
      transitionTimingFunction: {
        spring: 'cubic-bezier(0.34,1.56,0.64,1)',
      },
    },
  },
  plugins: [],
}
