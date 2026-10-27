import { fireEvent, render, screen } from '@testing-library/react'
import { BarChart3, Zap } from 'lucide-react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import Tabs from './Tabs'

const TABS = [{ id: 'basic', label: 'Básico', icon: BarChart3 }, { id: 'advanced', label: 'Avanzado', icon: Zap }, { id: 'rivals', label: 'Rivales' }]

function Controlled() {
  const [tab, setTab] = useState('basic')
  return <Tabs label="Vistas de equipo" tabs={TABS} value={tab} onChange={setTab} trailing={<span>extra</span>} />
}

// Issue #190: one row of tabs for the pages (Equipo, Administración, Jugadores… each had its own).
describe('Tabs (issue #190)', () => {
  it('is a tab list with the open tab selected', () => {
    render(<Controlled />)
    expect(screen.getByRole('tablist', { name: 'Vistas de equipo' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Básico' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Avanzado' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByText('extra')).toBeInTheDocument()                     // a control of the page at the end of the row
  })

  it('opens a tab with a click and moves with the arrows, Home and End', () => {
    render(<Controlled />)
    fireEvent.click(screen.getByRole('tab', { name: 'Rivales' }))
    expect(screen.getByRole('tab', { name: 'Rivales' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Rivales' }), { key: 'ArrowLeft' })
    expect(screen.getByRole('tab', { name: 'Avanzado' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Avanzado' })).toHaveFocus()
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Avanzado' }), { key: 'Home' })
    expect(screen.getByRole('tab', { name: 'Básico' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Básico' }), { key: 'End' })
    expect(screen.getByRole('tab', { name: 'Rivales' })).toHaveAttribute('aria-selected', 'true')
  })
})
