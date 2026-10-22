/** The next round of every competition (issues #286, #172, #440): the matches to follow, with filters and the teams "de interés" first. */
import { useMemo, useState } from 'react'
import { isFavorite, loadFavorites, toggleFavorite, type Favorite } from '../package/favorites'
import { NO_FILTERS, competitionOf, filterRounds, loadFilters, optionsOf, saveFilters, type RoundFilters } from '../package/filters'
import { competitionLabel, orderRounds, sidesOf, type RoundIndexEntry, type RoundMatch } from '../package/remote'

export { competitionLabel }

interface Props {
  rounds: RoundIndexEntry[]
  /** Can this device open the round (a password for the old ones, a right for the ones sealed by scope)? */
  canOpen: (round: RoundIndexEntry) => boolean
  /** `file#code#team` of the download in progress. */
  busy: string | null
  /** ``ownId``: the team whose point of view is followed (issue #286). */
  onDownload: (round: RoundIndexEntry, match: RoundMatch, ownId: string) => void
  /** Is this match, followed as this team, the package that is loaded now? (issue #342) */
  isLoaded: (code: string, ownId: string) => boolean
}

function when(start?: string | null): string {
  const d = start ? new Date(start) : null
  if (!d || Number.isNaN(d.getTime())) return 'fecha por confirmar'
  return `${d.toLocaleDateString('es-ES')} ${d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`
}

function Star({ team, favorites, onToggle }: { team: { id: string; name: string }; favorites: Favorite[]; onToggle: (team: Favorite) => void }) {
  const marked = isFavorite(favorites, team.id, team.name)
  return (
    <button type="button" className="star secondary" aria-pressed={marked} onClick={() => onToggle({ teamId: team.id, name: team.name })}
      aria-label={marked ? `Quitar ${team.name} de los equipos de interés` : `Marcar ${team.name} como de interés`}>
      {marked ? '★' : '☆'}
    </button>
  )
}

export default function RoundPackages({ rounds, canOpen, busy, onDownload, isLoaded }: Props) {
  const [favorites, setFavorites] = useState<Favorite[]>(() => loadFavorites())
  const [chosen, setChosen] = useState<RoundFilters>(() => loadFilters())
  const { competitions, groups: allGroups } = optionsOf(rounds, chosen.competition)
  // a remembered competition or group that is not published any more must not hide everything
  const competition = competitions.includes(chosen.competition) ? chosen.competition : ''
  const groups = competition ? allGroups : []
  const filters: RoundFilters = { ...chosen, competition, group: groups.includes(chosen.group) ? chosen.group : '' }
  const shown = useMemo(() => filterRounds(orderRounds(rounds, favorites), filters, favorites), [rounds, favorites, filters.competition, filters.group, filters.text, filters.onlyFavorites]) // eslint-disable-line react-hooks/exhaustive-deps

  if (rounds.length === 0) return null

  const change = (patch: Partial<RoundFilters>) => {
    const next = { ...filters, ...patch }
    setChosen(next)
    saveFilters(next)
  }
  const toggle = (team: Favorite) => {
    toggleFavorite(team)
    setFavorites(loadFavorites())
  }
  const filtered = JSON.stringify(filters) !== JSON.stringify(NO_FILTERS)

  return (
    <>
      <h2>Jornadas completas</h2>
      <p className="detail">Cualquier partido de la jornada, para seguirlo en directo. Primero tus equipos de interés (☆) y el partido de tu club.</p>
      <div className="round-filters" role="group" aria-label="Filtrar partidos">
        <label>
          Competición
          <select value={filters.competition} onChange={e => change({ competition: e.target.value, group: '' })}>
            <option value="">Todas</option>
            {competitions.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        {groups.length > 0 && (
          <label>
            Grupo
            <select value={filters.group} onChange={e => change({ group: e.target.value })}>
              <option value="">Todos</option>
              {groups.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </label>
        )}
        <label>
          Buscar equipo
          <input value={filters.text} onChange={e => change({ text: e.target.value })} autoComplete="off" autoCapitalize="off" spellCheck={false} />
        </label>
        <label className="round-filter-check">
          <input type="checkbox" checked={filters.onlyFavorites} onChange={e => change({ onlyFavorites: e.target.checked })} />
          Solo de interés
        </label>
        {filtered && <button type="button" className="secondary" onClick={() => change(NO_FILTERS)}>Quitar filtros</button>}
      </div>
      {shown.length === 0 && (
        <p className="detail">
          {filters.onlyFavorites && favorites.length === 0
            ? 'Todavía no has marcado ningún equipo: marca con la estrella (☆) los equipos que te interesan.'
            : 'Ningún partido coincide con los filtros.'}
        </p>
      )}
      {shown.map(round => (
        <section key={round.file} className="round-packages">
          <h3>{competitionOf(round).label}{round.round ? ` · jornada ${round.round}` : ''}</h3>
          <ul className="remote-packages">
            {round.matches.map(match => {
              const label = `${match.home.name} contra ${match.away.name}`
              const nameOf = (id: string) => (id === match.home.id ? match.home.name : id === match.away.id ? match.away.name : id)
              return (
                <li key={match.code} className="round-match">
                  <span className="round-info">
                    {[match.home, match.away].map(team => (
                      <span key={team.id} className="round-team">
                        <Star team={team} favorites={favorites} onToggle={toggle} />
                        {match.is_club ? <strong className="team-name">{team.name}</strong> : <span className="team-name">{team.name}</span>}
                      </span>
                    ))}
                    <span className="detail round-when">{when(match.start)}</span>
                  </span>
                  <span className="round-sides">
                    {sidesOf(match).map(id => {
                      const ready = isLoaded(match.code, id)
                      return (
                        <button key={id} aria-label={ready ? `${label} como ${nameOf(id)}: ya disponible` : `Descargar ${label} como ${nameOf(id)}`}
                          disabled={ready || !canOpen(round) || busy !== null} onClick={() => onDownload(round, match, id)}>
                          {ready ? 'Ya disponible' : busy === `${round.file}#${match.code}#${id}` ? 'Descargando…' : `Seguir como ${nameOf(id)}`}
                        </button>
                      )
                    })}
                  </span>
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </>
  )
}
