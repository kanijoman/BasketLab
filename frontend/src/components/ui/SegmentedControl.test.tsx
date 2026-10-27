import { fireEvent, render, screen } from '@testing-library/react'
import { Moon, Sun } from 'lucide-react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import SegmentedControl from './SegmentedControl'

const OPTIONS = [{ value: 'home', label: 'Local' }, { value: 'away', label: 'Visitante' }, { value: 'all', label: 'Todos' }]

function Controlled({ start = 'home' }: { start?: string }) {
  const [value, setValue] = useState(start)
  return <SegmentedControl label="Campo" options={OPTIONS} value={value} onChange={setValue} />
}

// Issue #190: one control for «choose one of a few» (there were ~30 groups of buttons, each with its own active style).
describe('SegmentedControl (issue #190)', () => {
  it('is a group of radios with the chosen one checked', () => {
    render(<Controlled />)
    expect(screen.getByRole('radiogroup', { name: 'Campo' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Local' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Visitante' })).toHaveAttribute('aria-checked', 'false')
  })

  it('changes with a click, and with the arrows from the keyboard (only the chosen one takes the Tab)', () => {
    render(<Controlled />)
    fireEvent.click(screen.getByRole('radio', { name: 'Visitante' }))
    expect(screen.getByRole('radio', { name: 'Visitante' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Visitante' })).toHaveAttribute('tabindex', '0')
    expect(screen.getByRole('radio', { name: 'Local' })).toHaveAttribute('tabindex', '-1')

    fireEvent.keyDown(screen.getByRole('radio', { name: 'Visitante' }), { key: 'ArrowRight' })
    expect(screen.getByRole('radio', { name: 'Todos' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Todos' })).toHaveFocus()
    fireEvent.keyDown(screen.getByRole('radio', { name: 'Todos' }), { key: 'ArrowRight' })      // wraps around
    expect(screen.getByRole('radio', { name: 'Local' })).toHaveAttribute('aria-checked', 'true')
  })

  it('with icons only, every option still has its name', () => {
    render(<SegmentedControl label="Tema" iconOnly value="light" onChange={() => undefined}
      options={[{ value: 'light', label: 'Claro', icon: Sun }, { value: 'dark', label: 'Oscuro', icon: Moon }]} />)
    expect(screen.getByRole('radio', { name: 'Oscuro' })).toHaveAttribute('title', 'Oscuro')
    expect(screen.queryByText('Oscuro')).toBeNull()
  })
})
