import { fireEvent, render as plainRender, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactElement } from 'react'
import { describe, expect, it, vi } from 'vitest'

const left = vi.hoisted(() => ({ byTeam: {} as Record<string, Set<string>> }))
vi.mock('@/lib/useLeftPlayers', () => ({ useLeftPlayers: (_collection: string | undefined, team: string) => (left.byTeam[team] ?? new Set<string>()) }))

import PlayerSelect from './PlayerSelect'

const render = (ui: ReactElement) => plainRender(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>)

describe('PlayerSelect layout (regression: the team dropdown overflowed the card on the right)', () => {
  it('lets the search box and the team dropdown shrink inside the card', () => {
    render(<PlayerSelect label="Jugador" value="" onChange={() => {}} players={[]}
      teams={[{ id: '1', name: 'MIPELLETYMAS B.F. LEON CON UN NOMBRE MUY LARGO' }]} />)
    const team = screen.getByDisplayValue('Todos los equipos')
    expect(team.className).toContain('min-w-0')
    expect(team.closest('div')?.className).toContain('max-w-[50%]')       // the box of the dropdown, which is the child of the row
    expect(screen.getByPlaceholderText(/buscar nombre/i).className).toContain('min-w-0')
    expect(screen.getByDisplayValue('— Selecciona jugador —').className).toContain('w-full')
  })
})

// Issue #711: an FBCYL player is listed by the actorId of one game, which changes from game to game; the analyses (IN/OUT, consistency) know him by his uuid. The option carries that.
describe('PlayerSelect: the key of a player (issue #711)', () => {
  const players = [
    { player_id: '872552', player_uuid: '593291b9-ff22-4545-b7b3-88159242a0d8', player_name: 'A. FBCYL', team_name: 'Alfa', team_id: '1' },
    { player_id: '9', player_name: 'B. FEB', team_name: 'Alfa', team_id: '1' },
  ]

  it('is his uuid when the table gives one (FBCYL) and his id otherwise (FEB)', () => {
    render(<PlayerSelect label="Jugador" value="" onChange={() => {}} players={players as never} teams={[]} />)
    expect(screen.getByRole('option', { name: /A\. FBCYL/ })).toHaveValue('593291b9-ff22-4545-b7b3-88159242a0d8')
    expect(screen.getByRole('option', { name: /B\. FEB/ })).toHaveValue('9')
  })
})

// #1082: choosing a team leaves out who has left it (a baja in his line of the FEB); «Todos los equipos» keeps everybody (a table of the league is not the list of a team).
describe('PlayerSelect: who has left the team chosen (issue #1082)', () => {
  const players = [
    { player_id: '1', player_name: 'A. SE FUE', team_name: 'Alfa', team_id: '101' },
    { player_id: '2', player_name: 'B. SIGUE', team_name: 'Alfa', team_id: '101' },
    { player_id: '1', player_name: 'A. SE FUE', team_name: 'Bravo', team_id: '102' },          // the same player, now in another team
  ]
  const names = () => screen.getAllByRole('option').map(o => o.textContent)

  it('hides him once the team is chosen, keeps him in the other team and in the list of everybody', () => {
    left.byTeam = { '101': new Set(['1']) }
    render(<PlayerSelect label="Jugador" collection="LF2" value="" onChange={() => {}} players={players as never} teams={[{ id: '101', name: 'Alfa' }, { id: '102', name: 'Bravo' }]} />)
    expect(names().join('|')).toContain('A. SE FUE (Alfa)')
    fireEvent.change(screen.getByLabelText('Jugador: filtrar por equipo'), { target: { value: '101' } })
    expect(names().join('|')).toContain('B. SIGUE')
    expect(names().join('|')).not.toContain('A. SE FUE')
    fireEvent.change(screen.getByLabelText('Jugador: filtrar por equipo'), { target: { value: '102' } })
    expect(names().join('|')).toContain('A. SE FUE (Bravo)')                                  // the baja is of his line for Alfa, not for Bravo
  })
})
