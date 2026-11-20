import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import vectors from '../../../tests/local_vectors/formation.json'
import type { EquivalenceDocument } from './equivalence'
import type { FormationDocument, FormationObs } from './formation'
import { FormationView } from './PlayerFormation'

/** The card «Si llega al sénior» (#893, E3c) over the documents the exporter writes (synthetic world of the tests): one estimate, a range, and always conditional on getting there. */
const doc = vectors.formation as unknown as FormationDocument
const equivalences = vectors.equivalences as unknown as EquivalenceDocument
const history = (vectors.cases as unknown as { history: FormationObs[]; estimate: unknown }[]).find(c => c.estimate)!.history

describe('the card of the index of the formation', () => {
  it('says the range of each of the eight axes with its centre', () => {
    render(<FormationView doc={doc} equivalences={equivalences} history={history} />)
    const rows = within(screen.getByRole('table', { name: /Margen esperado/ })).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(8)
    rows.forEach(r => expect(r.textContent).toMatch(/\d+–\d+ \(centro \d+\)/))
  })

  it('says that it is what is expected of those who get there and NOT the chance of getting there', () => {
    render(<FormationView doc={doc} equivalences={equivalences} history={history} />)
    expect(screen.getByText(/no es la probabilidad de llegar/)).toBeInTheDocument()
  })

  it('offers the senior competitions of his sex and changing it changes the numbers', async () => {
    render(<FormationView doc={doc} equivalences={equivalences} history={history} />)
    const select = screen.getByRole('combobox')
    const options = within(select).getAllByRole('option').map(o => (o as HTMLOptionElement).value)
    expect(options.length).toBeGreaterThan(1)
    const before = screen.getByRole('table').textContent
    await userEvent.selectOptions(select, options[options.length - 1])
    expect(screen.getByRole('table').textContent).not.toBe(before)
  })

  it('is indicative when the validation did not hold, and says nothing of it when it did', () => {
    const { unmount } = render(<FormationView doc={{ ...doc, usable: true }} equivalences={equivalences} history={history} />)
    expect(screen.queryByText('Orientativo')).toBeNull()
    unmount()
    render(<FormationView doc={{ ...doc, usable: false }} equivalences={equivalences} history={history} />)
    expect(screen.getByText('Orientativo')).toBeInTheDocument()
  })

  it('shows nothing for a group the index does not speak of or without formation', () => {
    const { container, unmount } = render(<FormationView doc={doc} equivalences={equivalences} history={[{ ...history[0], group: 'U12' }]} />)
    expect(container).toBeEmptyDOMElement()
    unmount()
    expect(render(<FormationView doc={doc} equivalences={equivalences} history={[]} />).container).toBeEmptyDOMElement()
  })
})
