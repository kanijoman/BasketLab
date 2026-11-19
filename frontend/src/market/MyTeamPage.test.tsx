import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { resetTalentData, setTalentBase } from './data'
import MyTeamPage from './MyTeamPage'
import { LF2_KEY, serveTalentData, TALENT_BASE } from '@/test/talentDataHost'

/** «Mi equipo» (#882) as the staff uses it, over the REAL publication of the exporter: the squad of a team of LF2 2025, its rotation, its holes and the searches that would fill them. */
beforeEach(() => { localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); serveTalentData() })

const Where = () => <p data-testid="where">{useLocation().search}</p>
const open = (search = '') => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[`/mi-equipo${search}`]}>
      <Routes><Route path="/mi-equipo" element={<><MyTeamPage /><Where /></>} /><Route path="/" element={<p>buscador</p>} /></Routes>
    </MemoryRouter>
  </QueryClientProvider>,
)
const mine = (team = '101') => `?c=${encodeURIComponent(LF2_KEY)}&e=${team}`

describe('«Mi equipo»', () => {
  it('asks to choose a team when none is chosen, and offers every competition published, senior or youth', async () => {
    open()
    expect(await screen.findByText(/Elige tu equipo/)).toBeInTheDocument()
    const options = within(screen.getByRole('combobox', { name: 'Competición' })).getAllByRole('option').map(o => o.textContent)
    expect(options.some(o => /L\.F\.-2/.test(o!))).toBe(true)
    expect(options.some(o => /Primera Nacional Femenina/.test(o!))).toBe(true)
  })

  it('chooses a competition and then a team, and puts both in the address and in the browser', async () => {
    open()
    await screen.findByText(/Elige tu equipo/)
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Competición' }), LF2_KEY)
    const team = await screen.findByRole('combobox', { name: 'Equipo' })
    await waitFor(() => expect(within(team).getAllByRole('option').length).toBeGreaterThan(1))          // the teams come when the rows of the competition do
    await userEvent.selectOptions(team, (within(team).getAllByRole('option')[1] as HTMLOptionElement).value)
    await waitFor(() => expect(screen.getByTestId('where').textContent).toMatch(/e=/))
    expect(JSON.parse(localStorage.getItem('talent-my-team')!)).toMatchObject({ comp: LF2_KEY })
  })

  it('shows the rotation by minutes, the holes of profile and the age of the squad', async () => {
    open(mine())
    const rotation = await screen.findByRole('table', { name: /Rotación/ })
    expect(within(rotation).getAllByRole('row').length).toBeGreaterThan(5)
    const profile = screen.getByRole('list', { name: 'Huecos de perfil' })
    expect(within(profile).getAllByRole('listitem')).toHaveLength(3)
    expect(screen.getByText(/menores de 22/i)).toBeInTheDocument()
  })

  it('says how many players have no position and does not call that a hole', async () => {
    open(mine())
    await screen.findByRole('table', { name: /Rotación/ })
    expect(screen.getByText(/sin posición/i)).toBeInTheDocument()
    expect(screen.queryByText(/Hueco de posición/i)).not.toBeInTheDocument()
  })

  it('offers, for each weak axis, a search with the filters already put (percentile 75, minutes enough)', async () => {
    open(mine())
    const link = (await screen.findAllByRole('link', { name: /Buscar jugadores de/ }))[0]
    const url = new URL(link.getAttribute('href')!, 'https://x.test')
    expect(url.searchParams.get('p')).toBe('75')
    expect(url.searchParams.get('e')).toBe('1')
    expect(url.searchParams.get('s')).toBe('2025')
    expect(url.searchParams.get('m')).toBeTruthy()
  })

  it('remembers the team: with an empty address it opens the one chosen last time', async () => {
    localStorage.setItem('talent-my-team', JSON.stringify({ comp: LF2_KEY, team: '101' }))
    open()
    expect(await screen.findByRole('table', { name: /Rotación/ })).toBeInTheDocument()
  })

  it('says so when the team of the address is not in the competition, instead of an empty page', async () => {
    open(mine('nadie'))
    expect(await screen.findByText(/No encontramos ese equipo/)).toBeInTheDocument()
  })

  it('says it when the publication is not there yet', async () => {
    serveTalentData().override['index.json'] = null
    open()
    expect(await screen.findByText(/Aún no hay datos de jugadores publicados/)).toBeInTheDocument()
  })
})
