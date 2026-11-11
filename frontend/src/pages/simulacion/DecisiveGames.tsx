/** The decisive games of the reader's team (issue #850): the matches still to play whose result moves its expected position the most, and what each result does to it (and to a cut line, if one is drawn). */
import { pct } from '@/forecast/copy'
import { decisiveGames, type Cut, type Result } from '@/forecast/decisive'
import type { SeasonSim } from '@/forecast/seasonSim'
import Card from '@/components/ui/Card'
import { whenText } from '../previa/format'
import { cutLabel } from './rows'

const one = (x: number): string => x.toFixed(1).replace('.', ',')

function resultText(who: string, r: Result, cut?: Cut): string {
  const chance = cut && r.pCut !== null ? ` · ${pct(r.pCut, 0)} de estar ${cutLabel(cut).toLowerCase()}` : ''
  return `${who}: puesto medio ${one(r.meanPosition)}${chance}`
}

export default function DecisiveGames({ sim, team, cut }: { sim: SeasonSim; team: string; cut?: Cut }) {
  const games = decisiveGames(sim, team, cut)
  return (
    <section aria-label="Partidos decisivos" className="space-y-3">
      <h2 className="text-lg font-semibold text-ink">Partidos decisivos de {sim.names[team]}</h2>
      <p className="text-sm text-ink-muted">Los partidos por jugar cuyo resultado más mueve el puesto que se espera para este equipo (también los de otros equipos: su resultado cambia la tabla).</p>
      <ul className="grid gap-3 lg:grid-cols-2">
        {games.map(g => {
          const f = g.fixture
          const home = f.home === team
          const lines = g.involvesTeam
            ? [resultText('Si ganamos', home ? g.ifHomeWins : g.ifAwayWins, cut), resultText('Si perdemos', home ? g.ifAwayWins : g.ifHomeWins, cut)]
            : [resultText(`Si gana ${f.homeName}`, g.ifHomeWins, cut), resultText(`Si gana ${f.awayName}`, g.ifAwayWins, cut)]
          return (
            <li key={f.code} data-testid="decisive">
              <Card title={`${f.homeName} – ${f.awayName}`} padding="md">
                <p className="text-xs text-ink-muted">Jornada {f.round} · {whenText(f.start)}</p>
                <ul className="mt-2 space-y-1 text-sm text-ink">{lines.map(l => <li key={l}>{l}</li>)}</ul>
              </Card>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
