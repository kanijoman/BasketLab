import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { resetTalentData, setTalentBase } from './data'
import ComparePage from './ComparePage'
import { serveTalentData, TALENT_BASE } from '@/test/talentDataHost'

/** The comparator (B5, #881) as the staff uses it, over the REAL publication of the exporter. */
beforeEach(() => { localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); serveTalentData() })

const Where = () => <p data-testid="where">{useLocation().search}</p>

const open = (search = '') => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[`/comparar${search}`]}>
      <Routes><Route path="/comparar" element={<><ComparePage /><Where /></>} /><Route path="/" element={<p>buscador</p>} /></Routes>
    </MemoryRouter>
  </QueryClientProvider>,
)

describe('the comparison page', () => {
  it('puts two players side by side: bio, figures and the percentile of every axis, with one radar and the numbers beside it', async () => {
    open('?j=feb:10100,feb:10200')
    const table = await screen.findByRole('table', { name: /Comparación de jugadores/ })
    expect(within(table).getByRole('columnheader', { name: /ANA PRUEBA UNO/ })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: /BEA PRUEBA DOS/ })).toBeInTheDocument()
    expect(within(table).getByRole('rowheader', { name: 'Altura' })).toBeInTheDocument()
    expect(within(table).getByRole('rowheader', { name: /Cuidar el balón/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Comparación de ANA PRUEBA UNO, BEA PRUEBA DOS/ })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /Tabla de comparación/ })).toHaveAttribute('tabindex', '0')          // a scrollable table is reachable with the keyboard on a phone (axe: scrollable-region-focusable)
  })

  it('has a column with the difference (the second minus the first) only when there are two players (#1009)', async () => {
    open('?j=feb:10101,feb:10200')
    const table = await screen.findByRole('table', { name: /Comparación de jugadores/ })
    expect(within(table).getByRole('columnheader', { name: /Diferencia/ })).toBeInTheDocument()
    expect(within(table).getByRole('rowheader', { name: 'Partidos' }).closest('tr')!.textContent).toMatch(/[+−]\d|0$/)
  })

  it('has no difference column with three players, and can be exported (#1009)', async () => {
    open('?j=feb:10100,feb:10200,fbcyl:34001-00')
    const table = await screen.findByRole('table', { name: /Comparación de jugadores/ })
    expect(within(table).queryByRole('columnheader', { name: /Diferencia/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Exportar/ })).toBeInTheDocument()
  })

  it('warns that every percentile is the one of the player in his own competition and season', async () => {
    open('?j=feb:10100,feb:10200')
    expect(await screen.findByText(/nunca se compara entre competiciones/i)).toBeInTheDocument()
  })

  it('compares players of different leagues: a FBCYL player is read in her own competition', async () => {
    open('?j=feb:10200,fbcyl:34001-00')
    const table = await screen.findByRole('table', { name: /Comparación de jugadores/ })
    expect(within(table).getAllByText(/Primera Nacional Femenina/).length).toBeGreaterThan(0)
    expect(within(table).getAllByText(/L\.F\.-2/).length).toBeGreaterThan(0)
  })

  it('adds a player found by name to the address, takes one out, and does not offer a fourth', async () => {
    open('?j=feb:10100')
    await screen.findByRole('button', { name: /Quitar ANA PRUEBA UNO/ })
    await userEvent.type(screen.getByRole('searchbox', { name: /Añadir jugador/ }), 'bea')
    await userEvent.click(await screen.findByRole('button', { name: /BEA PRUEBA DOS/ }))
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent(/j=feb%3A10100%2Cfeb%3A10200|j=feb:10100,feb:10200/))
    await userEvent.click(screen.getByRole('button', { name: /Quitar ANA PRUEBA UNO/ }))
    await waitFor(() => expect(screen.getByTestId('where')).not.toHaveTextContent(/10100/))
  })

  it('does not take a fourth player: with three the box is off and says why', async () => {
    open('?j=feb:10100,feb:10200,fbcyl:34001-00')
    await screen.findByRole('table', { name: /Comparación de jugadores/ })
    expect(screen.getByRole('searchbox', { name: /Añadir jugador/ })).toBeDisabled()
    expect(screen.getByText(/Ya hay 3 jugadores/)).toBeInTheDocument()
  })

  it('says what to do with nobody chosen, and which player could not be found', async () => {
    open()
    expect(await screen.findByText(/Elige de dos a tres jugadores/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Volver al buscador/ })).toHaveAttribute('href', '/')
  })

  it('says it when a player of the address does not exist', async () => {
    open('?j=feb:10100,feb:no-existe')
    expect(await screen.findByText(/No encontramos a feb:no-existe/)).toBeInTheDocument()
  })

  it('says it when the publication is not there yet', async () => {
    const host = serveTalentData()
    host.override['index.json'] = null
    open('?j=feb:10100')
    expect(await screen.findByText(/Aún no hay datos de jugadores publicados/)).toBeInTheDocument()
  })
})
