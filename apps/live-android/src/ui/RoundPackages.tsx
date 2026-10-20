/** The next round of every competition (issues #286, #172): the matches to follow, the club's competition and match first. */
import { orderRounds, sidesOf, type RoundIndexEntry, type RoundMatch } from '../package/remote'

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

/** `LF_CHALLENGE_2026_2027_Liga_Regular_Único` -> `LF CHALLENGE 2026 2027 Liga Regular Único`. */
export function competitionLabel(collection: string): string {
  return collection.replace(/_+/g, ' ').trim()
}

function when(start?: string | null): string {
  const d = start ? new Date(start) : null
  if (!d || Number.isNaN(d.getTime())) return 'fecha por confirmar'
  return `${d.toLocaleDateString('es-ES')} ${d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`
}

export default function RoundPackages({ rounds, canOpen, busy, onDownload, isLoaded }: Props) {
  if (rounds.length === 0) return null
  return (
    <>
      <h2>Jornadas completas</h2>
      <p className="detail">Cualquier partido de la jornada, para seguirlo en directo. Primero la competición y el partido de tu club.</p>
      {orderRounds(rounds).map(round => (
        <section key={round.file} className="round-packages">
          <h3>{competitionLabel(round.collection)}{round.round ? ` · jornada ${round.round}` : ''}</h3>
          <ul className="remote-packages">
            {round.matches.map(match => {
              const label = `${match.home.name} contra ${match.away.name}`
              const nameOf = (id: string) => (id === match.home.id ? match.home.name : id === match.away.id ? match.away.name : id)
              return (
                <li key={match.code} className="round-match">
                  <span>
                    {match.is_club ? <strong>{match.home.name} – {match.away.name}</strong> : <>{match.home.name} – {match.away.name}</>}
                    <span className="detail"> · {when(match.start)}</span>
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
