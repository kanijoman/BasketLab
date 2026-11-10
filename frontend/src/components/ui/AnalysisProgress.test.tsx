import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import AnalysisProgress from './AnalysisProgress'

describe('AnalysisProgress', () => {
  it('shows the message and the percentage with a bar of that width', () => {
    const { container } = render(<AnalysisProgress progress={40} />)
    expect(screen.getByText(/Analizando partidos/)).toBeInTheDocument()
    expect(screen.getByText('40%')).toBeInTheDocument()
    expect(container.querySelector('[style*="width: 40%"]')).not.toBeNull()
  })

  it('shows only the message while the progress is not known', () => {
    const { container } = render(<AnalysisProgress progress={null} />)
    expect(screen.getByText(/Analizando partidos/)).toBeInTheDocument()
    expect(screen.queryByText(/%/)).toBeNull()
    expect(container.querySelector('[style*="width"]')).toBeNull()
  })
})
