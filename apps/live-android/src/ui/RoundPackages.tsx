/** The next round of every competition (issues #286, #172): the matches to follow, the club's competition and match first. */
import { orderRounds, type RoundIndexEntry, type RoundMatch } from '../package/remote'

interface Props {
  rounds: RoundIndexEntry[]
  pass: string
  /** `file#code` of the download in progress. */
  busy: string | null
  onDownload: (round: RoundIndexEntry, match: RoundMatch) => void
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

export default function RoundPackages({ rounds, pass, busy, onDownload }: Props) {
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
              return (
                <li key={match.code}>
                  <span>
                    {match.is_club ? <strong>{match.home.name} – {match.away.name}</strong> : <>{match.home.name} – {match.away.name}</>}
                    <span className="detail"> · {when(match.start)}</span>
                  </span>
                  <button aria-label={`Descargar ${label}`} disabled={!pass || busy !== null} onClick={() => onDownload(round, match)}>
                    {busy === `${round.file}#${match.code}` ? 'Descargando…' : 'Descargar'}
                  </button>
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </>
  )
}
