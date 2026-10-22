/** The demo matches of the Partidos tab (issues #476, #477): open one, or get its PDF report. The matches kept on the device (finished, recorded) have their own panels. */
import { useState } from 'react'
import { demoLabel, orderDemos, type DemoMatch } from '../engine/demo'
import type { Favorite } from '../package/favorites'

export const SAMPLE_SOURCE = 'sample'

interface Props {
  demos: DemoMatch[]
  favorites: Favorite[]
  hasSample: boolean
  /** The match that is open now (a code of the manifest, or `sample`). */
  source: string
  /** A live connection is running: leaving it would drop the match being followed. */
  disabled: boolean
  onView: (source: string) => void
  /** The code of the report being built (it disables the other buttons). */
  reporting: string | null
  onReport: (source: string) => void
  error: string | null
}

export default function MatchLibrary({ demos, favorites, hasSample, source, disabled, onView, reporting, onReport, error }: Props) {
  const [competition, setCompetition] = useState('')
  const [team, setTeam] = useState('')
  const competitions = [...new Set(demos.flatMap(m => (m.competition ? [m.competition] : [])))].sort()
  const ofCompetition = demos.filter(m => !competition || m.competition === competition)
  const teams = [...new Set(ofCompetition.flatMap(m => [m.home.name, m.away.name]))].sort((a, b) => a.localeCompare(b, 'es'))
  const shown = ofCompetition.filter(m => !team || m.home.name === team || m.away.name === team)
  const filtered = competition !== '' || team !== ''
  const items = [...orderDemos(shown, favorites).map(m => ({ value: m.code, label: demoLabel(m) })),
    ...(hasSample && !filtered ? [{ value: SAMPLE_SOURCE, label: 'Partido de ejemplo' }] : [])]
  if (demos.length === 0 && items.length === 0) return null
  return (
    <section className="panel match-library" aria-label="Partidos de demostración">
      <h2>Partidos de demostración</h2>
      <p className="detail">Para probar la app sin un partido en directo: se reproducen como si fueran en vivo. Los de tus equipos de interés van primero.</p>
      <div className="round-filters" role="group" aria-label="Filtrar demostraciones">
        {competitions.length > 0 && (
          <label>
            Competición
            <select value={competition} onChange={e => { setCompetition(e.target.value); setTeam('') }}>
              <option value="">Todas</option>
              {competitions.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        )}
        <label>
          Equipo
          <select value={team} onChange={e => setTeam(e.target.value)}>
            <option value="">Todos</option>
            {teams.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
      </div>
      {items.length === 0 && <p className="detail">Ninguna demostración coincide con los filtros.</p>}
      <ul className="remote-packages">
        {items.map(item => (
          <li key={item.value}>
            <span>{item.label}</span>
            <span className="round-sides">
              <button type="button" aria-label={`Ver ${item.label}`} disabled={disabled || item.value === source} onClick={() => onView(item.value)}>
                {item.value === source ? 'Viendo' : 'Ver'}
              </button>
              <button type="button" className="secondary" aria-label={`Informe PDF de ${item.label}`} disabled={disabled || reporting !== null} onClick={() => onReport(item.value)}>
                {reporting === item.value ? 'Generando informe…' : 'Informe PDF'}
              </button>
            </span>
          </li>
        ))}
      </ul>
      {disabled && <p className="detail">Desconecta antes de abrir una demostración o generar su informe.</p>}
      {error && <p role="alert" className="status error">{error}</p>}
    </section>
  )
}
