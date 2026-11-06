/** Show / remove the preparation package that is loaded (it comes from the published list; no file and no password). */
import type { PackageStore } from '../package/storage'
import type { PackageSummary } from '../package/summary'
import HelpHint from './HelpHint'

interface Props {
  store: PackageStore
  loaded?: PackageSummary | null
  onRemoved?: () => void
  /** The loaded match is not the one on the Partido tab (a demo is open): the panel offers to go back to it (issue #509). */
  viewing?: boolean
  onOpenLoaded?: () => void
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('es-ES')
}

function formatDateTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : `${d.toLocaleDateString('es-ES')} ${d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`
}

export default function PackagePanel({ store, loaded, onRemoved, viewing = true, onOpenLoaded }: Props) {
  async function remove() {
    await store.clear()
    onRemoved?.()
  }

  return (
    <section className="panel">
      <h2>Paquete de preparación</h2>
      <HelpHint label="Ayuda sobre el paquete de preparación">
        Contiene las estadísticas de la temporada de los dos equipos y los umbrales de las reglas. En directo, el motor las
        compara con lo que pasa en la pista para proponer alertas. Se actualiza solo 3 veces al día; con «Quitar paquete»
        vuelves al partido de demostración.
      </HelpHint>
      {loaded ? (
        <div className="package-summary">
          <p><strong>{loaded.team}</strong> vs <strong>{loaded.rival}</strong></p>
          {loaded.match && (
            <p className="detail">
              Partido: {loaded.match.home && loaded.match.away ? `${loaded.match.home.name.trim()} vs ${loaded.match.away.name.trim()}` : 'sin detalles'}
              {loaded.match.start ? ` · ${formatDateTime(loaded.match.start)}` : ''} (código {loaded.match.code})
            </p>
          )}
          <p className="detail">
            Temporada {loaded.season} · creado el {formatDate(loaded.createdAt)} · {loaded.ownPlayers} jugadores propios,
            {' '}{loaded.rivalPlayers} rivales · partidos: {loaded.games.own} propios, {loaded.games.rival} rival,
            {' '}{loaded.games.league} de la liga
          </p>
          {loaded.crossDivision && (
            <p className="detail">Equipos de divisiones distintas: sus estadísticas se midieron contra rivales de distinto nivel. El valor previo se ha corregido con la diferencia entre divisiones (estimada con partidos de Copa), pero la probabilidad de victoria sigue siendo aproximada.</p>
          )}
          {!viewing && onOpenLoaded && <button type="button" onClick={onOpenLoaded}>Ver el partido del paquete</button>}
          <button className="secondary" onClick={() => void remove()}>Quitar paquete</button>
        </div>
      ) : (
        <p className="detail">Sin paquete: se usa el partido de demostración.</p>
      )}
    </section>
  )
}
