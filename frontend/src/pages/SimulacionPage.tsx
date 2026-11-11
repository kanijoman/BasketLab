/**
 * Simulación de la liga (issue #850): the final positions of the league, from the matches still to play of the REAL calendar played 10,000 times. A table of what is expected of every team, a heat
 * map of the final positions, the cut lines the reader draws (promotion, play-off and relegation rules change with the competition and the season: none is modelled, and no configuration lives
 * in the repository) and the decisive games of the reader's own team. The own team is the one chosen in the preview; the lines are remembered in this browser only.
 */
import { useState, type ReactNode } from 'react'
import { CalendarX2, ListOrdered } from 'lucide-react'
import { leagueRows } from './simulacion/rows'
import type { Cut } from '@/forecast/decisive'
import { loadPrefs, savePrefs } from '@/forecast/storage'
import { useForecast } from '@/forecast/useForecast'
import { useSeasonSim } from '@/forecast/useSeasonSim'
import { useCollection } from '@/context/CollectionContext'
import EmptyState from '@/components/ui/EmptyState'
import PageHeader from '@/components/ui/PageHeader'
import PageTransition from '@/components/ui/PageTransition'
import Spinner from '@/components/ui/Spinner'
import { Field, Select } from '@/components/ui/Field'
import CutLines from './simulacion/CutLines'
import DecisiveGames from './simulacion/DecisiveGames'
import PositionHeatmap from './simulacion/PositionHeatmap'
import ProjectionTable from './simulacion/ProjectionTable'

export default function SimulacionPage() {
  const { collection } = useCollection()
  const name = collection?.name
  const { model, calendar, teams, isLoading, error } = useForecast(name)
  const sim = useSeasonSim(model, calendar)
  const [prefs, setPrefs] = useState(() => (name ? loadPrefs(name) : { cuts: [] as Cut[] }))

  const header = <PageHeader title="Simulación de la liga" subtitle={collection?.label} icon={ListOrdered} />
  const wrap = (body: ReactNode) => <PageTransition><div className="space-y-5">{header}{body}</div></PageTransition>
  if (isLoading || (!model && !error)) return wrap(<Spinner />)
  if (error) return wrap(<p role="alert" className="rounded-lg border border-bad/30 bg-bad/10 p-3 text-sm text-bad">{error instanceof Error ? error.message : String(error)}</p>)
  if (!calendar) return wrap(<EmptyState icon={CalendarX2} title="Esta competición todavía no tiene el calendario publicado." description="La simulación necesita los partidos que quedan por jugar." />)
  if (!sim) return wrap(<Spinner />)

  const save = (change: Partial<typeof prefs>) => { if (name) savePrefs(name, change); setPrefs(p => ({ ...p, ...change })) }
  const own = prefs.team && sim.teams.includes(prefs.team) ? prefs.team : null
  const rows = leagueRows(sim, prefs.cuts)
  const over = sim.remaining.length === 0

  return wrap(
    <>
      <p className="text-sm text-ink-muted">
        {over ? 'No quedan partidos por jugar: esta es la clasificación final.' : `Se juegan ${sim.n.toLocaleString('es-ES')} veces los ${sim.remaining.length} partidos que quedan.`}
      </p>
      <p className="text-sm text-ink-muted">No se modelan ascensos, descensos ni playoffs: las reglas cambian con la competición y la temporada. Dibuja tú las líneas de corte que te interesen.</p>
      {!over && (
        <div className="card flex flex-wrap items-end gap-4 p-4">
          <Field label="Tu equipo">
            <Select aria-label="Tu equipo" value={own ?? ''} onChange={e => save({ team: e.target.value || undefined })}>
              <option value="">Ninguno</option>
              {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </Select>
          </Field>
          <CutLines cuts={prefs.cuts} teams={sim.teams.length} onChange={cuts => save({ cuts })} />
        </div>
      )}
      <section aria-label="Clasificación" className="space-y-2">
        <h2 className="text-lg font-semibold text-ink">Clasificación proyectada</h2>
        <ProjectionTable rows={rows} cuts={prefs.cuts} ownTeam={own} />
      </section>
      <section aria-label="Puestos finales" className="space-y-2">
        <h2 className="text-lg font-semibold text-ink">Puestos finales</h2>
        <p className="text-xs text-ink-muted">En cada casilla, el porcentaje de temporadas simuladas en que el equipo acaba en ese puesto (1 es el primero).</p>
        <PositionHeatmap sim={sim} rows={rows} />
      </section>
      {!over && own && <DecisiveGames sim={sim} team={own} cut={prefs.cuts[0]} />}
      {!over && !own && <p className="text-sm text-ink-muted">Elige tu equipo para ver los partidos que más le pueden mover en la tabla.</p>}
      <details className="card p-4 text-sm text-ink-muted">
        <summary className="cursor-pointer font-medium text-ink">Cómo se calcula</summary>
        <div className="mt-2 space-y-2">
          <p>Cada equipo tiene una puntuación que se actualiza con los resultados de la competición (contando también los que el calendario ya tiene aunque aún no estén en las estadísticas), con su margen de error. En cada temporada simulada se sortea la fuerza real de cada equipo dentro de ese margen y, desde ella, el resultado de cada partido que queda, con la ventaja de campo de la competición.</p>
          <p>La clasificación se ordena por victorias; si hay empate, por los partidos entre los empatados, por la diferencia de puntos de toda la liga y, si aún no se distinguen, por sorteo. Es una aproximación: las bases de cada competición pueden desempatar de otra forma.</p>
          <p>Las líneas de corte no se guardan en el repositorio: se recuerdan solo en este navegador.</p>
        </div>
      </details>
    </>,
  )
}
