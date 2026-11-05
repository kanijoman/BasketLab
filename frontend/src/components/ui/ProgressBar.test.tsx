import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ProgressBar from './ProgressBar'

// Issue #215: one progress component for the long downloads (the weekly report ZIP and the individual scouting DOCX).
describe('ProgressBar', () => {
  it('is a progressbar that says how far it is, and says what it is doing with the step of the total', () => {
    render(<ProgressBar step={3} total={12} message="Gráficos" />)
    const bar = screen.getByRole('progressbar', { name: 'Gráficos (3/12)' })
    expect(bar).toHaveAttribute('aria-valuenow', '3')
    expect(bar).toHaveAttribute('aria-valuemax', '12')
    expect(screen.getByText('Gráficos (3/12)')).toBeInTheDocument()
  })

  it('without a total it shows only the message, empty', () => {
    render(<ProgressBar step={0} total={0} message="Iniciando…" />)
    expect(screen.getByText('Iniciando…')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
  })

  it('never goes past the end', () => {
    render(<ProgressBar step={9} total={5} message="x" />)
    expect(screen.getByRole('progressbar').firstElementChild).toHaveStyle({ width: '100%' })
  })
})
