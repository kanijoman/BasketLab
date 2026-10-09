import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PlayerSelect from './PlayerSelect'

describe('PlayerSelect layout (regression: the team dropdown overflowed the card on the right)', () => {
  it('lets the search box and the team dropdown shrink inside the card', () => {
    render(<PlayerSelect label="Jugador" value="" onChange={() => {}} players={[]}
      teams={[{ id: '1', name: 'MIPELLETYMAS B.F. LEON CON UN NOMBRE MUY LARGO' }]} />)
    const team = screen.getByDisplayValue('Todos los equipos')
    expect(team.className).toContain('min-w-0')
    expect(team.className).toContain('max-w-[50%]')
    expect(screen.getByPlaceholderText(/buscar nombre/i).className).toContain('min-w-0')
    expect(screen.getByDisplayValue('— Selecciona jugador —').className).toContain('w-full')
  })
})
