/** The matches to follow (issues #286, #172, #440, #511): the next match of each team, filtered by league, competition, group and team, the teams "de interés" first. */
import { useMemo, useState } from 'react'
import { isFavorite, loadFavorites, toggleFavorite, type Favorite } from '../package/favorites'
import { NO_FILTERS, competitionOf, loadFilters, optionsOf, saveFilters, type RoundFilters } from '../package/filters'
import { competitionLabel, type RoundIndexEntry, type RoundMatch } from '../package/remote'
import { nextMatchesOfFavorites, nextMatchList } from '../package/upcoming'
import { LEAD_OPTIONS } from '../notify/schedule'
import Select from './Select'
import { useReminders, type ReminderLoader } from './useReminders'

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
  /** Is the loaded match the one on the Partido tab? When it is not (a demo is open), the loaded match offers «Ver este partido» (issue #509). */
  viewing?: boolean
  onOpenLoaded?: () => void
  /** The moment the next matches are counted from (tests). */
  now?: Date
  /** The notifications plugin (issue #482); the real one when absent (tests give a fake). */
  reminders?: ReminderLoader
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

function Reminders({ next, now, reminders }: { next: ReturnType<typeof nextMatchesOfFavorites>; now: Date; reminders?: ReminderLoader }) {
  const reminder = useReminders(next, now, reminders)
  if (next.length === 0) return null
  return (
    <section className="panel reminders" aria-label="Avisos de los partidos de interés">
      <label className="round-filter-check">
        <input type="checkbox" checked={reminder.prefs.enabled} onChange={e => reminder.update({ enabled: e.target.checked })} />
        Avisarme antes de los partidos de mis equipos de interés
      </label>
      {reminder.prefs.enabled && (
        <Select label="Minutos antes" value={String(reminder.prefs.leadMin)} onChange={v => reminder.update({ leadMin: Number(v) })}
          options={LEAD_OPTIONS.map(m => ({ value: String(m), label: String(m) }))} />
      )}
      {reminder.prefs.enabled && reminder.result?.ok && <p className="detail">{reminder.result.scheduled === 1 ? '1 aviso programado' : `${reminder.result.scheduled} avisos programados`}.</p>}
      {reminder.result && !reminder.result.ok && (
        <p className="detail" role="status">
          {reminder.result.reason === 'denied' ? 'Tienes las notificaciones desactivadas para la app: actívalas en los ajustes del sistema.'
            : reminder.result.reason === 'unavailable' ? 'Los avisos solo funcionan en la app instalada, no en el navegador.' : 'Falta el permiso de notificaciones.'}
        </p>
      )}
    </section>
  )
}

export default function RoundPackages({ rounds, canOpen, busy, onDownload, isLoaded, viewing = true, onOpenLoaded, now, reminders }: Props) {
  const [favorites, setFavorites] = useState<Favorite[]>(() => loadFavorites())
  const [chosen, setChosen] = useState<RoundFilters>(() => loadFilters())
  // a remembered league, competition, group or team that is not published any more must not hide everything: each one is checked against what is on offer
  const checked = (f: RoundFilters): RoundFilters => {
    const leagues = optionsOf(rounds, { ...NO_FILTERS }).leagues
    const league = leagues.includes(f.league) ? f.league : ''
    const competition = optionsOf(rounds, { ...NO_FILTERS, league }).competitions.includes(f.competition) ? f.competition : ''
    const group = optionsOf(rounds, { ...NO_FILTERS, league, competition }).groups.includes(f.group) ? f.group : ''
    const team = optionsOf(rounds, { ...NO_FILTERS, league, competition, group }).teams.some(t => t.id === f.team) ? f.team : ''
    return { ...f, league, competition, group, team }
  }
  const filters = checked(chosen)
  const { leagues, competitions, groups, teams } = optionsOf(rounds, filters)
  const moment = now ?? new Date()
  const shown = useMemo(() => nextMatchList(rounds, filters, favorites, moment), [rounds, favorites, filters.league, filters.competition, filters.group, filters.team, moment.getTime()]) // eslint-disable-line react-hooks/exhaustive-deps
  const nextOfInterest = nextMatchesOfFavorites(rounds, favorites, now)

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
  const filtered = filters.league !== '' || filters.competition !== '' || filters.group !== '' || filters.team !== ''

  return (
    <>
      <p className="detail">
        {filtered ? 'Los partidos que coinciden con los filtros; primero los de tus equipos de interés (☆).'
          : favorites.length > 0 ? 'El próximo partido de tus equipos de interés (☆). Con los filtros ves el de otros equipos.'
            : 'Marca equipos de interés (☆) y aquí verás su próximo partido; mientras tanto, el próximo partido de cada equipo.'}
      </p>
      <Reminders next={nextOfInterest} now={moment} reminders={reminders} />
      <div className="round-filters" role="group" aria-label="Filtrar partidos">
        {leagues.length > 0 && (
          <Select label="Liga" value={filters.league} onChange={v => change({ league: v, competition: '', group: '', team: '' })}
            options={[{ value: '', label: 'Todas' }, ...leagues.map(l => ({ value: l, label: l }))]} />
        )}
        <Select label="Competición" value={filters.competition} onChange={v => change({ competition: v, group: '', team: '' })}
          options={[{ value: '', label: 'Todas' }, ...competitions.map(c => ({ value: c, label: c }))]} />
        {groups.length > 0 && (
          <Select label="Grupo" value={filters.group} onChange={v => change({ group: v, team: '' })}
            options={[{ value: '', label: 'Todos' }, ...groups.map(g => ({ value: g, label: g }))]} />
        )}
        {filters.competition && teams.length > 0 && (
          <Select label="Equipo" value={filters.team} onChange={v => change({ team: v })}
            options={[{ value: '', label: 'Todos' }, ...teams.map(t => ({ value: t.id, label: t.name }))]} />
        )}
        {filtered && <button type="button" className="secondary" onClick={() => change(NO_FILTERS)}>Quitar filtros</button>}
      </div>
      {shown.length === 0 && (
        <p className="detail">{filtered ? 'Ningún partido coincide con los filtros.' : 'No hay partidos por jugar en las jornadas publicadas.'}</p>
      )}
      <ul className="remote-packages match-list">
        {shown.map(({ round, match, sides }) => {
          const label = `${match.home.name} contra ${match.away.name}`
          const nameOf = (id: string) => (id === match.home.id ? match.home.name : id === match.away.id ? match.away.name : id)
          return (
            <li key={match.code} className="round-match" data-code={match.code}>
              <span className="round-info">
                <span className="detail round-competition">{competitionOf(round).label}</span>
                {[match.home, match.away].map(team => (
                  <span key={team.id} className="round-team">
                    <Star team={team} favorites={favorites} onToggle={toggle} />
                    {match.is_club ? <strong className="team-name">{team.name}</strong> : <span className="team-name">{team.name}</span>}
                  </span>
                ))}
                <span className="detail round-when">{when(match.start)}</span>
              </span>
              <span className="round-sides">
                {sides.map(id => {
                  const ready = isLoaded(match.code, id)
                  if (ready && !viewing && onOpenLoaded) {
                    return <button key={id} aria-label={`Ver este partido: ${label} como ${nameOf(id)}`} onClick={onOpenLoaded}>Ver este partido</button>
                  }
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
    </>
  )
}
