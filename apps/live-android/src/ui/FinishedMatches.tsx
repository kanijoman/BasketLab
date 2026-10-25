import type { FinishedMatch } from '../feed/finishedStore'
import { useMatchFilters } from './MatchFilters'
import RemoveButton from './RemoveButton'

/** The live matches that ended and were kept on the device (issue #407): each one can be reviewed again. */
interface Props {
  matches: FinishedMatch[]
  /** A live connection is running: leaving it would drop the match being followed. */
  disabled: boolean
  onReview: (code: string) => void
  /** The post-match analysis as a PDF (issue #409); the code of the one being built disables the buttons. */
  onReport: (code: string) => void
  /** Deletes a saved match (issue #512; the button asks first). */
  onRemove: (code: string) => void
  reporting: string | null
  error: string | null
}

const date = (iso: string) => new Date(iso).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' })

/** «Local – Visitante»: the teams of the title (the saved match has no other record of them). */
const teamsOf = (title: string) => title.split(' – ').map(t => t.trim()).filter(Boolean)

export default function FinishedMatches({ matches, disabled, onReview, onReport, onRemove, reporting, error }: Props) {
  const { shown, controls } = useMatchFilters(matches, m => ({ competition: m.competition, teams: teamsOf(m.title) }), 'Filtrar partidos finalizados')
  if (matches.length === 0) return null
  return (
    <section className="panel finished-matches" aria-label="Partidos finalizados">
      <h2>Partidos finalizados</h2>
      <p className="detail">Guardados en este dispositivo al terminar el partido, para revisarlos cuando quieras.</p>
      {matches.length > 1 && controls}
      {shown.length === 0 && <p className="detail">Ningún partido finalizado coincide con los filtros.</p>}
      <ul className="remote-packages">
        {shown.map(m => (
          <li key={m.code}>
            <span className="round-info">
              {m.competition && <span className="detail round-competition">{m.competition}</span>}
              <strong className="match-title">{m.title}</strong>
              <span className="detail round-when">{date(m.savedAt)}{m.complete === false && ' · incompleto (se dejó de seguir antes del final)'}</span>
            </span>
            <span className="round-sides">
              <button type="button" className="secondary" aria-label={`Revisar ${m.title}`} disabled={disabled || reporting !== null} onClick={() => onReview(m.code)}>
                Revisar
              </button>
              <button type="button" className="secondary" aria-label={`Informe PDF de ${m.title}`} disabled={disabled || reporting !== null}
                onClick={() => onReport(m.code)}>
                {reporting === m.code ? 'Generando informe…' : 'Informe'}
              </button>
              <RemoveButton what={m.title} disabled={disabled || reporting !== null} onConfirm={() => onRemove(m.code)} />
            </span>
          </li>
        ))}
      </ul>
      {disabled && <p className="detail">Desconecta antes de revisar un partido finalizado o generar su informe.</p>}
      {error && <p role="alert" className="status error">{error}</p>}
    </section>
  )
}
