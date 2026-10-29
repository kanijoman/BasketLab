import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import Checkbox from './Checkbox'

// Issue #193: a checkbox named by its label, so the series of a chart and the filters are read by a screen reader and clicked on their text.
function Controlled({ onChange = vi.fn() }: { onChange?: (on: boolean) => void }) {
  const [on, setOn] = useState(false)
  return <Checkbox label="Media móvil" checked={on} onChange={e => { setOn(e.target.checked); onChange(e.target.checked) }} />
}

describe('Checkbox', () => {
  it('is a checkbox named by its text', () => {
    render(<Controlled />)
    expect(screen.getByRole('checkbox', { name: 'Media móvil' })).not.toBeChecked()
  })

  it('turns on and off from its box and from its text', () => {
    const changed = vi.fn()
    render(<Controlled onChange={changed} />)
    fireEvent.click(screen.getByRole('checkbox', { name: 'Media móvil' }))
    expect(screen.getByRole('checkbox', { name: 'Media móvil' })).toBeChecked()
    fireEvent.click(screen.getByText('Media móvil'))
    expect(screen.getByRole('checkbox', { name: 'Media móvil' })).not.toBeChecked()
    expect(changed.mock.calls).toEqual([[true], [false]])
  })

  it('a disabled one is disabled for the screen reader and looks it (the browser does not change it: jsdom would fire the click)', () => {
    render(<Checkbox label="No disponible" checked={false} disabled onChange={() => undefined} />)
    expect(screen.getByRole('checkbox', { name: 'No disponible' })).toBeDisabled()
    expect(screen.getByText('No disponible').closest('label')).toHaveClass('cursor-not-allowed')
  })

  it('takes the classes of the row it is in and any native attribute', () => {
    render(<Checkbox label="Liga" className="ml-auto" defaultChecked data-x="1" />)
    expect(screen.getByText('Liga').closest('label')).toHaveClass('ml-auto')
    expect(screen.getByRole('checkbox', { name: 'Liga' })).toHaveAttribute('data-x', '1')
  })
})
