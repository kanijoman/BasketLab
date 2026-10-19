import type { FinishedMatch } from '../feed/finishedStore'

/** The live matches that ended and were kept on the device (issue #407): each one can be reviewed again. */
interface Props {
  matches: FinishedMatch[]
  /** A live connection is running: leaving it would drop the match being followed. */
  disabled: boolean
  onReview: (code: string) => void
  /** The post-match analysis as a PDF (issue #409); the code of the one being built disables the buttons. */
  onReport: (code: string) => void
  reporting: string | null
  error: string | null
}

const date = (iso: string) => new Date(iso).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' })

export default function FinishedMatches({ matches, disabled, onReview, onReport, reporting, error }: Props) {
  if (matches.length === 0) return null
  return (
    <section className="panel finished-matches" aria-label="Partidos finalizados">
      <h2>Partidos finalizados</h2>
      <p className="detail">Guardados en este dispositivo al terminar el partido, para revisarlos cuando quieras.</p>
      <ul className="remote-packages">
        {matches.map(m => (
          <li key={m.code}>
            <span>{m.title} <span className="detail">· {date(m.savedAt)}</span></span>
            <span className="round-sides">
              <button type="button" className="secondary" disabled={disabled || reporting !== null} onClick={() => onReview(m.code)}>
                Revisar {m.title}
              </button>
              <button type="button" className="secondary" aria-label={`Informe PDF de ${m.title}`} disabled={disabled || reporting !== null}
                onClick={() => onReport(m.code)}>
                {reporting === m.code ? 'Generando informe…' : 'Informe PDF'}
              </button>
            </span>
          </li>
        ))}
      </ul>
      {disabled && <p className="detail">Desconecta antes de revisar un partido finalizado o generar su informe.</p>}
      {error && <p role="alert" className="status error">{error}</p>}
    </section>
  )
}
