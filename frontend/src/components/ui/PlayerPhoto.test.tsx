import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EXPORT_HIDE_ATTR, EXPORT_ONLY_ATTR } from '@/lib/exportDom'
import PlayerPhoto from './PlayerPhoto'

describe('PlayerPhoto (#1010)', () => {
  it('shows the photo with the name as its text and keeps an initials chip only for the export', () => {
    const { container } = render(<PlayerPhoto name="ANA BEATRIZ CASTRO" src="https://imagenes.feb.es/foto.aspx?c=1" />)
    expect(screen.getByRole('img', { name: 'ANA BEATRIZ CASTRO' })).toHaveAttribute('src', 'https://imagenes.feb.es/foto.aspx?c=1')
    expect(container.querySelector(`[${EXPORT_HIDE_ATTR}]`)).not.toBeNull()          // html2canvas cannot paint a cross-origin photo: it is swapped for the initials on export
    expect(container.querySelector(`[${EXPORT_ONLY_ATTR}]`)?.textContent).toBe('AB')
  })

  it('falls back to the initials when the photo does not load, and says so to nobody (no broken image)', () => {
    render(<PlayerPhoto name="ANA BEATRIZ CASTRO" src="https://imagenes.feb.es/foto.aspx?c=1" />)
    fireEvent.error(screen.getByRole('img', { name: 'ANA BEATRIZ CASTRO' }))
    expect(screen.queryByRole('img', { name: 'ANA BEATRIZ CASTRO' })).not.toBeInTheDocument()
    expect(screen.getByText('AB')).toBeInTheDocument()
  })

  it('shows the initials when there is no photo address at all', () => {
    render(<PlayerPhoto name="J1. ALPHA" src={null} />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('JA')).toBeInTheDocument()
  })

  it('is as big as asked for', () => {
    const { container } = render(<PlayerPhoto name="ANA" src={null} size={72} />)
    expect((container.firstElementChild as HTMLElement).style.width).toBe('72px')
  })
})
