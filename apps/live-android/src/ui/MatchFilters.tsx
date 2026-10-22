/** Competition and team filters shared by the lists of demos and finished matches (issues #474, #497). */
import { useState } from 'react'

export interface Filterable {
  competition?: string
  teams: string[]
}

export interface MatchFilterState<T> {
  shown: T[]
  filtered: boolean
  controls: JSX.Element
}

/** Filters `items`: the competition narrows the teams offered, and a team that does not play in a newly chosen competition is dropped. */
export function useMatchFilters<T>(items: T[], describe: (item: T) => Filterable, label: string): MatchFilterState<T> {
  const [competition, setCompetition] = useState('')
  const [team, setTeam] = useState('')
  const competitions = [...new Set(items.flatMap(i => describe(i).competition ?? []))].sort()
  const ofCompetition = items.filter(i => !competition || describe(i).competition === competition)
  const teams = [...new Set(ofCompetition.flatMap(i => describe(i).teams))].sort((a, b) => a.localeCompare(b, 'es'))
  const activeTeam = teams.includes(team) ? team : ''
  const shown = ofCompetition.filter(i => !activeTeam || describe(i).teams.includes(activeTeam))
  const controls = (
    <div className="round-filters" role="group" aria-label={label}>
      {competitions.length > 0 && (
        <label>
          Competición
          <select value={competition} onChange={e => setCompetition(e.target.value)}>
            <option value="">Todas</option>
            {competitions.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
      )}
      <label>
        Equipo
        <select value={activeTeam} onChange={e => setTeam(e.target.value)}>
          <option value="">Todos</option>
          {teams.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>
    </div>
  )
  return { shown, filtered: competition !== '' || activeTeam !== '', controls }
}
