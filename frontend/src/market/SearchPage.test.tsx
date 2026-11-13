import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { resetTalentData, setTalentBase } from './data'
import SearchPage from './SearchPage'
import { LF2_KEY, readTalent, serveTalentData, TALENT_BASE } from '@/test/talentDataHost'
import type { WebDataHost } from '@/test/webDataHost'

/** The search of Talent (B3, #879) as the staff uses it, over the REAL publication of the exporter: LF2 2025 (with bio) and FBCYL 2026 (without). */
let host: WebDataHost
beforeEach(() => { localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); host = serveTalentData() })

const open = (path = '/') => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><SearchPage /></MemoryRouter>
  </QueryClientProvider>,
)

/** The manifest as if both competitions were of the same season, to be able to mix them in the page. */
const sameSeason = () => {
  const manifest = JSON.parse(readTalent('index.json'))
  manifest.competitions.forEach((c: { season: string; season_label: string }) => { c.season = '2026'; c.season_label = '2026/2027' })
  host.override['index.json'] = JSON.stringify(manifest)
}

/** The manifest as if LF2 were a youth competition (the real catalogue marks the six youth championships of FEB the same way), to see how the page names and groups it. */
const youthLf2 = () => {
  const manifest = JSON.parse(readTalent('index.json'))
  const lf2 = manifest.competitions.find((c: { key: string }) => c.key === LF2_KEY)
  Object.assign(lf2, { category: 'formacion', age_group: 'U16', competition_label: 'Campeonato juvenil de prueba · Cadete femenino' })
  host.override['index.json'] = JSON.stringify(manifest)
}

describe('the search page', () => {
  it('starts on the latest season published with its competitions, and says how many players it found', async () => {
    open()
    expect(await screen.findByRole('heading', { level: 1, name: /Buscador/ })).toBeInTheDocument()
    expect(await screen.findByText(/\d+ jugadoras? encontrad|\d+ jugadores? encontrad/i)).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /Temporada/i })).toHaveValue('2026')
    expect(screen.getByRole('checkbox', { name: /Primera Nacional Femenina/ })).toBeChecked()
    expect(screen.queryByRole('checkbox', { name: /L\.F\.-2/ })).not.toBeInTheDocument()       // it is of another season
  })

  it('changing the season shows the competitions of that season and its players', async () => {
    open()
    await userEvent.selectOptions(await screen.findByRole('combobox', { name: /Temporada/i }), '2025')
    expect(await screen.findByText('ANA PRUEBA UNO')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /L\.F\.-2/ })).toBeChecked()
  })

  it('hides the players without the data a filter asks for, says how many, and brings them back on request', async () => {
    open('/?s=2026')
    await screen.findByText(/encontrad/i)                                    // FBCYL has no date of birth
    await userEvent.type(screen.getByRole('spinbutton', { name: /Edad mínima/i }), '18')
    expect(await screen.findByText(/0 jugadores? encontrad/i)).toBeInTheDocument()
    expect(screen.getByText(/ocultos? por no tener el dato/i)).toBeInTheDocument()
    expect(screen.getByText(/edad/i, { selector: '[data-testid="hidden-detail"]' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: /Incluir los que no tienen el dato/i }))
    expect(await screen.findByText(/[1-9]\d* jugadores? encontrad/i)).toBeInTheDocument()
    expect(screen.queryByText(/ocultos? por no tener el dato/i)).not.toBeInTheDocument()
  })

  it('filters the players of LF2 by age and by the group of position', async () => {
    open('/?s=2025')
    expect(await screen.findByText('ANA PRUEBA UNO')).toBeInTheDocument()
    await userEvent.type(screen.getByRole('spinbutton', { name: /Edad mínima/i }), '30')
    await waitFor(() => expect(screen.queryByText('ANA PRUEBA UNO')).not.toBeInTheDocument())      // 21 years on 31/12/2025
    await userEvent.clear(screen.getByRole('spinbutton', { name: /Edad mínima/i }))
    expect(await screen.findByText('ANA PRUEBA UNO')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: /^Pívots$/ }))
    await waitFor(() => expect(screen.queryByText('ANA PRUEBA UNO')).not.toBeInTheDocument())     // Ana is a guard
  })

  it('warns when the competitions chosen are not alike, and the warning goes with the choice', async () => {
    sameSeason()
    open('/?s=2026')
    expect(await screen.findByText(/no se pueden comparar entre ellas/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: /Primera Nacional Femenina/ }))
    await waitFor(() => expect(screen.queryByText(/no se pueden comparar entre ellas/i)).not.toBeInTheDocument())
  })

  it('opens a shared link with its filters in the boxes', async () => {
    open('/?s=2025&amin=18&amax=25&pos=G&u=1&q=ana')
    expect(await screen.findByText('ANA PRUEBA UNO')).toBeInTheDocument()
    expect(screen.getByRole('spinbutton', { name: /Edad mínima/i })).toHaveValue(18)
    expect(screen.getByRole('spinbutton', { name: /Edad máxima/i })).toHaveValue(25)
    expect(screen.getByRole('checkbox', { name: /^Bases y escoltas$/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /Incluir los que no tienen el dato/i })).toBeChecked()
  })

  it('offers the CSV of what is on the screen', async () => {
    open('/?s=2025')
    await screen.findByText('ANA PRUEBA UNO')
    expect(screen.getByRole('button', { name: /Exportar/i })).toBeInTheDocument()
  })

  it('says there is no data yet when nothing is published, and when a competition cannot be opened it says which', async () => {
    host.override['index.json'] = null
    const first = open()
    expect(await screen.findByText(/Aún no hay datos de jugadores publicados/)).toBeInTheDocument()
    first.unmount()
    resetTalentData(); host.override = {}
    const lf2 = JSON.parse(readTalent('index.json')).competitions.find((c: { key: string }) => c.key === LF2_KEY)
    host.override[lf2.file] = null
    open('/?s=2025')
    expect(await screen.findByText(/No se ha podido abrir L\.F\.-2/)).toBeInTheDocument()
  })

  it('has the table named for the screen reader', async () => {
    open('/?s=2025')
    const table = await screen.findByRole('region', { name: /Jugadores encontrados/i })
    expect(await within(table).findByText('ANA PRUEBA UNO')).toBeInTheDocument()
  })

  it('groups the competitions by category and names them as the catalogue does, in the boxes and in the table (#914)', async () => {
    youthLf2()
    open('/?s=2025')
    const youth = await screen.findByRole('group', { name: 'Formación' })
    expect(within(youth).getByRole('checkbox', { name: /Campeonato juvenil de prueba · Cadete femenino/ })).toBeChecked()
    expect(screen.queryByRole('checkbox', { name: /^L\.F\.-2/ })).not.toBeInTheDocument()            // its name is the label, not the code
    expect(screen.queryByRole('group', { name: 'Sénior' })).not.toBeInTheDocument()                    // nothing senior in this season
    expect(await screen.findByText('ANA PRUEBA UNO')).toBeInTheDocument()
  })

  it('a season with both categories shows both groups, Sénior first, and the senior one is what a competition without category is', async () => {
    const manifest = JSON.parse(readTalent('index.json'))
    manifest.competitions.forEach((c: { season: string; season_label: string }) => { c.season = '2026'; c.season_label = '2026/2027' })
    Object.assign(manifest.competitions.find((c: { key: string }) => c.key === LF2_KEY), { category: 'formacion', age_group: 'U18', competition_label: 'Júnior de prueba' })
    host.override['index.json'] = JSON.stringify(manifest)
    open('/?s=2026')
    await screen.findByText(/encontrad/i)
    expect(screen.getAllByRole('group').map(g => g.getAttribute('aria-label')).filter(Boolean)).toEqual(['Sénior', 'Formación'])
    expect(within(screen.getByRole('group', { name: 'Sénior' })).getByRole('checkbox', { name: /Primera Nacional Femenina/ })).toBeInTheDocument()     // FBCYL has no category in the manifest
  })
})
