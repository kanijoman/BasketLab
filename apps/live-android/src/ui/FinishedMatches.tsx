import type { FinishedMatch } from '../feed/finishedStore'

/** The live matches that ended and were kept on the device (issue #407): each one can be reviewed again. */
interface Props {
  matches: FinishedMatch[]
  /** A live connection is running: leaving it would drop the match being followed. */
  disabled: boolean
  onReview: (code: string) => void
}

const date = (iso: string) => new Date(iso).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' })

export default function FinishedMatches({ matches, disabled, onReview }: Props) {
  if (matches.length === 0) return null
  return (
    <section className="panel finished-matches" aria-label="Partidos finalizados">
      <h2>Partidos finalizados</h2>
      <p className="detail">Guardados en este dispositivo al terminar el partido, para revisarlos cuando quieras.</p>
      <ul className="remote-packages">
        {matches.map(m => (
          <li key={m.code}>
            <span>{m.title} <span className="detail">· {date(m.savedAt)}</span></span>
            <button type="button" className="secondary" disabled={disabled} onClick={() => onReview(m.code)}>
              Revisar {m.title}
            </button>
          </li>
        ))}
      </ul>
      {disabled && <p className="detail">Desconecta antes de revisar un partido finalizado.</p>}
    </section>
  )
}
