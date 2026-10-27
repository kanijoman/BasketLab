import { fireEvent, render, screen } from '@testing-library/react'
import { Download, Trash2 } from 'lucide-react'
import { describe, expect, it, vi } from 'vitest'
import Button, { IconButton } from './Button'

// Issue #190: one button for the whole web (there were 77 raw <button> and 20 .btn-* with their own styles).
describe('Button (issue #190)', () => {
  it.each([['primary', 'btn-primary'], ['secondary', 'btn-secondary'], ['ghost', 'btn-ghost'], ['danger', 'btn-danger']] as const)(
    'variant %s draws with %s', (variant, cls) => {
      render(<Button variant={variant}>Guardar</Button>)
      expect(screen.getByRole('button', { name: 'Guardar' })).toHaveClass(cls)
    })

  it('is a plain button by default: it never submits a form by accident', () => {
    const submit = vi.fn(e => e.preventDefault())
    render(<form onSubmit={submit}><Button>Filtrar</Button></form>)
    fireEvent.click(screen.getByRole('button', { name: 'Filtrar' }))
    expect(submit).not.toHaveBeenCalled()
    expect(screen.getByRole('button')).toHaveAttribute('type', 'button')
  })

  it('while loading it is busy, cannot be pressed twice and says so', () => {
    const click = vi.fn()
    render(<Button loading icon={Download} onClick={click}>Exportar</Button>)
    const button = screen.getByRole('button', { name: /Exportar/ })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status', { name: 'Cargando' })).toBeInTheDocument()
    fireEvent.click(button)
    expect(click).not.toHaveBeenCalled()
  })

  it('the small size is smaller', () => {
    render(<Button size="sm">Ver</Button>)
    expect(screen.getByRole('button', { name: 'Ver' })).toHaveClass('text-xs')
  })
})

describe('IconButton (issue #190)', () => {
  it('has a name for the screen reader and the tooltip, though it only shows an icon', () => {
    render(<IconButton icon={Trash2} label="Eliminar colección" />)
    const button = screen.getByRole('button', { name: 'Eliminar colección' })
    expect(button).toHaveAttribute('title', 'Eliminar colección')
    expect(button.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  })
})
