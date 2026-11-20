import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import vectors from '../../../tests/local_vectors/equivalence.json'
import { EquivalenceView } from './PlayerEquivalence'
import type { EquivalenceDocument, EstimateOrigin } from './equivalence'

/** The card «En otra competición» (#891, E4) over the REAL document of the exporter (the sample of movers): one estimate, always a range, never a single figure. */
const doc = vectors.document as unknown as EquivalenceDocument
type Case = { history: EstimateOrigin[]; to: string; estimate: unknown[] | null }
const cases = vectors.cases as unknown as Case[]
const one = cases.find(c => c.estimate && (c.estimate[0] as { seasons: number }).seasons === 1)!
const two = cases.find(c => c.estimate && (c.estimate[0] as { seasons: number }).seasons === 2)!

describe('the card of the equivalences', () => {
  it('says the range of each of the eight axes with its centre, in the competition he is translated to', () => {
    render(<EquivalenceView doc={doc} history={one.history} />)
    const table = screen.getByRole('table', { name: /Margen esperado/ })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(8)
    rows.forEach(r => expect(r.textContent).toMatch(/\d+–\d+ \(centro \d+\)/))
  })

  it('says which seasons it is built from, without letting the reader choose', () => {
    const { unmount } = render(<EquivalenceView doc={doc} history={one.history} />)
    expect(screen.getByText(/a partir de su última temporada/)).toBeInTheDocument()
    unmount()
    render(<EquivalenceView doc={doc} history={two.history} />)
    expect(screen.getByText(/la media de sus dos últimas temporadas/)).toBeInTheDocument()
    expect(screen.queryByRole('radio')).toBeNull()
  })

  it('offers the competitions connected to his, never his own, and changing it changes the numbers', async () => {
    render(<EquivalenceView doc={doc} history={one.history} />)
    const select = screen.getByRole('combobox')
    const options = within(select).getAllByRole('option').map(o => (o as HTMLOptionElement).value)
    expect(options).not.toContain(one.history[one.history.length - 1].node)
    expect(options.length).toBeGreaterThan(1)
    const before = screen.getByRole('table').textContent
    await userEvent.selectOptions(select, options[options.length - 1])
    expect(screen.getByRole('table').textContent).not.toBe(before)
  })

  it('is indicative when the validation did not hold, and says nothing of it when it did', () => {
    const { unmount } = render(<EquivalenceView doc={{ ...doc, usable: true }} history={one.history} />)
    expect(screen.queryByText('Orientativo')).toBeNull()
    unmount()
    render(<EquivalenceView doc={{ ...doc, usable: false }} history={one.history} />)
    expect(screen.getByText('Orientativo')).toBeInTheDocument()
  })

  it('says why there is no translation for a player outside the graph instead of leaving a gap', () => {
    render(<EquivalenceView doc={doc} history={[]} />)
    expect(screen.getByText(/Sin traducción/)).toBeInTheDocument()
    expect(screen.queryByRole('table')).toBeNull()
  })
})
