import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import TeamLogo from './TeamLogo'

const TEAM = { id: '1008898', name: 'RECOLETAS ZAMORA' }

describe('TeamLogo', () => {
  it('first tries the logo bundled in the app (it also works without a connection)', () => {
    render(<TeamLogo team={TEAM} />)
    const img = screen.getByRole('img', { name: /recoletas zamora/i }) as HTMLImageElement
    expect(img.getAttribute('src')).toBe('./logos/1008898.png')
  })

  it('falls back to FEB when the bundled one is missing, and then to the initials', () => {
    render(<TeamLogo team={TEAM} />)
    fireEvent.error(screen.getByRole('img', { name: /recoletas zamora/i }))
    expect((screen.getByRole('img', { name: /recoletas zamora/i }) as HTMLImageElement).getAttribute('src'))
      .toBe('https://imagenes.feb.es/imagen.aspx?i=1008898&ti=1')
    fireEvent.error(screen.getByRole('img', { name: /recoletas zamora/i }))
    expect(screen.queryByRole('img', { name: /recoletas zamora/i })).toBeNull()
    expect(screen.getByLabelText(/recoletas zamora/i).textContent).toBe('RZ')
  })

  it('the size is configurable and the image does not block the layout', () => {
    render(<TeamLogo team={TEAM} size={48} />)
    const img = screen.getByRole('img', { name: /recoletas zamora/i }) as HTMLImageElement
    expect(img.getAttribute('width')).toBe('48')
    expect(img.getAttribute('loading')).toBe('lazy')
  })
})
