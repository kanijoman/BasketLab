/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // MetricsForAll brand colors (basketball orange + dark court)
        primary: {
          50:  '#fff7ed',
          100: '#ffedd5',
          500: '#f97316',
          600: '#ea580c',
          700: '#c2410c',
        },
        court: {
          950: '#0c1a0e',
          900: '#14271a',
          800: '#1c3524',
        },
      },
    },
  },
  plugins: [],
}
