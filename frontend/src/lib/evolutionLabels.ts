/**
 * Text of the series of the chart of Evolución. The series are keyed by team ID (`<id>_raw`, `<id>_avg`, `<id>_cum`) and the competition's
 * (`comp_rolling`, `comp_cumulative`); the staff reads the NAME of the team, in the legend under the chart and in the tooltip.
 */
export function seriesLabel(key: string, teamName: (id: string) => string, window: number): string {
  if (key === 'comp_rolling') return `Liga (media ${window}J)`
  if (key === 'comp_cumulative') return 'Liga (acumulado)'
  const team = teamName(key.replace(/_raw$|_avg$|_cum$/, ''))
  if (key.endsWith('_avg')) return `${team} (media ${window}J)`
  if (key.endsWith('_cum')) return `${team} (acumulado)`
  return `${team} (partido)`
}
