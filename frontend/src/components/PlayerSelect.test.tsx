import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PlayerSelect from './PlayerSelect'

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
