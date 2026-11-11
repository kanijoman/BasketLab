/**
 * The heat map of the final positions (issue #850): a row per team, a column per position, and in each cell the share of the simulated seasons in which the team ended there. An accessible table
 * (caption, headers by row and column, the exact share in `data-p` and in the title of the cell) that scrolls sideways on a phone with the team in a sticky first column (a region with a name and focus, so that the keyboard can scroll it). The fill is the accent
 * at up to 60 %, so the ink of the page keeps the contrast on it in both themes.
 */
import type { SeasonSim } from '@/forecast/seasonSim'
import type { LeagueRow } from './rows'

const MAX_ALPHA = 0.6

export default function PositionHeatmap({ sim, rows }: { sim: SeasonSim; rows: LeagueRow[] }) {
  const positions = Array.from({ length: sim.teams.length }, (_, i) => i + 1)
  return (
    <div role="region" tabIndex={0} aria-label="Puestos finales por equipo" className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full border-collapse text-xs">
        <caption className="sr-only">Probabilidad de cada puesto final</caption>
        <thead>
          <tr>
            <th scope="col" className="sticky left-0 z-10 bg-surface px-2 py-1.5 text-left font-medium text-ink-muted">Equipo</th>
            {positions.map(p => <th key={p} scope="col" className="px-1.5 py-1.5 text-center font-medium text-ink-muted">{p}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => {
            const counts = sim.positionCounts[sim.teams.indexOf(row.team_id)]
            return (
              <tr key={row.team_id} className="border-t border-line/40">
                <th scope="row" className="sticky left-0 z-10 max-w-[10rem] truncate bg-surface px-2 py-1 text-left font-medium text-ink" title={row.team_name}>{row.team_name}</th>
                {positions.map(p => {
                  const share = counts[p - 1] / sim.n
                  return (
                    <td key={p} data-p={share} title={`${row.team_name}, puesto ${p}: ${(share * 100).toFixed(1).replace('.', ',')} %`}
                      className="px-1.5 py-1 text-center tabular-nums text-ink" style={{ backgroundColor: `rgb(var(--accent-rgb) / ${Math.min(MAX_ALPHA, share * 1.5)})` }}>
                      {share >= 0.005 ? Math.round(share * 100) : ''}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
