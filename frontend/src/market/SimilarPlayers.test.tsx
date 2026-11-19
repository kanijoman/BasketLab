import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import SimilarList from './SimilarPlayers'
import { ENOUGH_MINUTES } from './enoughMinutes'
import type { SimilarResult } from './similar'
import type { SearchRow } from './search'

const row = (over: Partial<SearchRow> = {}): SearchRow => ({ person_id: 'feb:2', name: 'B. C', full_name: 'BEA CASTRO', team_id: 't', team_name: 'ALFA', age: 21, minutes: 1200, comp_key: 'k', competition: 'LF2', season: '2025', season_label: '2025/2026', ...over }) as SearchRow
const show = (result: SimilarResult, target = 'feb:1') => render(<MemoryRouter><SimilarList result={result} targetId={target} loading={false} /></MemoryRouter>)

describe('the card of the players like him (#1010)', () => {
  it('says each one with his team, his age, the similarity as a percentage and a way to compare with him', () => {
    show({ similar: [{ row: row(), similarity: 91.3, axes: 8 }], reason: null })
    const item = within(screen.getByRole('list', { name: 'Jugadores parecidos' })).getByRole('listitem')
    expect(within(item).getByRole('link', { name: 'BEA CASTRO' })).toHaveAttribute('href', '/jugador/feb%3A2')
    expect(item).toHaveTextContent('ALFA')
    expect(item).toHaveTextContent('21 años')
    expect(item).toHaveTextContent('91 %')
    expect(within(item).getByRole('link', { name: /Comparar con BEA CASTRO/ })).toHaveAttribute('href', '/comparar?j=feb%3A1%2Cfeb%3A2')
  })

  it('shows a dash for an age nobody knows, never «0 años»', () => {
    show({ similar: [{ row: row({ age: null }), similarity: 80, axes: 7 }], reason: null })
    expect(screen.queryByText(/0 años/)).not.toBeInTheDocument()
    expect(screen.getByTitle('Sin dato')).toBeInTheDocument()
  })

  it('explains how it is worked out, and that the competition is the same one', () => {
    show({ similar: [{ row: row(), similarity: 90, axes: 8 }], reason: null })
    expect(screen.getByText(/Solo se comparan jugadores de la misma competición y temporada/)).toBeInTheDocument()
    expect(screen.getByText(/100 menos la diferencia media/)).toBeInTheDocument()
  })

  it('says why there are none: few minutes (with the rule), no profile, or nobody close enough', () => {
    const { unmount } = show({ similar: [], reason: 'few-minutes' })
    expect(screen.getByText(new RegExp(ENOUGH_MINUTES.slice(0, 20)))).toBeInTheDocument()
    unmount()
    const none = show({ similar: [], reason: 'no-profile' })
    expect(screen.getByText(/sin perfil/i)).toBeInTheDocument()
    none.unmount()
    show({ similar: [], reason: null })
    expect(screen.getByText(/Ningún jugador de la competición tiene un perfil comparable/)).toBeInTheDocument()
  })
})
