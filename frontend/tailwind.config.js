import preset from '../design/tailwind-preset.cjs'

/**
 * The colours, shadows and fonts come from the shared preset over design/tokens.css (issue #188): every name changes with the theme
 * (light by default, dark, or the system's). Only the geometry of the web stays here.
 * @type {import('tailwindcss').Config}
 */
export default {
  presets: [preset],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      borderRadius: {
        DEFAULT: '0.5rem',
        card:    '0.75rem',
        pill:    '9999px',
      },
      transitionTimingFunction: {
        spring: 'cubic-bezier(0.34,1.56,0.64,1)',
      },
    },
  },
  plugins: [],
}
