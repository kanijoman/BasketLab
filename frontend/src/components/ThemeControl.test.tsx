import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import ThemeControl from './ThemeControl'
import { THEME_KEY } from '@/lib/theme'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

// Issue #188: where to choose the theme of the web: light (the default), dark or the device's.
describe('ThemeControl (issue #188)', () => {
  it('offers the three themes with light chosen by default', () => {
    render(<ThemeControl />)
    const group = screen.getByRole('radiogroup', { name: 'Tema' })
    expect(group).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Claro' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Oscuro' })).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByRole('radio', { name: 'Sistema' })).toHaveAttribute('aria-checked', 'false')
  })

  it('applies and remembers the one chosen', () => {
    render(<ThemeControl />)
    fireEvent.click(screen.getByRole('radio', { name: 'Oscuro' }))
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    expect(screen.getByRole('radio', { name: 'Oscuro' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Claro' })).toHaveAttribute('aria-checked', 'false')
  })
})
