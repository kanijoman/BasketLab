import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import Radio from './Radio'

// Issue #195: a radio named by its label, for a long option (a match with its date and rival) that does not fit a SegmentedControl.
function Group() {
  const [v, setV] = useState('a')
  return (
    <>
      <Radio name="g" label="Primero" checked={v === 'a'} onChange={() => setV('a')} />
      <Radio name="g" label="Segundo" checked={v === 'b'} onChange={() => setV('b')} />
    </>
  )
}

describe('Radio', () => {
  it('is a radio named by its text, chosen from its circle and from its text', () => {
    render(<Group />)
    expect(screen.getByRole('radio', { name: 'Primero' })).toBeChecked()
    fireEvent.click(screen.getByText('Segundo'))
    expect(screen.getByRole('radio', { name: 'Segundo' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Primero' })).not.toBeChecked()
  })

  it('a disabled one is disabled and looks it, and the label takes the classes of its row', () => {
    render(<Radio label="No" checked={false} disabled onChange={() => undefined} className="ml-auto" />)
    expect(screen.getByRole('radio', { name: 'No' })).toBeDisabled()
    expect(screen.getByText('No').closest('label')).toHaveClass('cursor-not-allowed', 'ml-auto')
  })
})
