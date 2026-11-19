import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { loadCompetitionRows, resetTalentData, setTalentBase } from './data'
import PlayerPage from './PlayerPage'
import { FBCYL_KEY, LF2_KEY, readTalent, serveTalentData, TALENT_BASE } from '@/test/talentDataHost'
import type { WebDataHost } from '@/test/webDataHost'

/** The profile of a player (B4, #880) as the staff reads it, over the REAL publication of the exporter: LF2 2025 (with bio) and FBCYL 2026 (without). */
let host: WebDataHost
beforeEach(() => { localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); host = serveTalentData() })

const open = (personId: string) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[`/jugador/${encodeURIComponent(personId)}`]}>
      <Routes><Route path="/jugador/:personId" element={<PlayerPage />} /><Route path="/" element={<p>buscador</p>} /></Routes>
    </MemoryRouter>
  </QueryClientProvider>,
)

const ANA = 'feb:10100'

describe('the profile page', () => {
  it('names the player, says his bio and lists his season with the competition and the team', async () => {
    open(ANA)
    expect(await screen.findByRole('heading', { level: 1, name: /ANA PRUEBA UNO/ })).toBeInTheDocument()
    const trajectory = (await screen.findByRole('heading', { name: /Trayectoria/ })).closest('section')!
    expect(within(trajectory).getByText(/2025\/2026/)).toBeInTheDocument()
    expect(within(trajectory).getByText(/L\.F\.-2/)).toBeInTheDocument()
    expect(screen.getByText(/Altura/)).toBeInTheDocument()
  })

  it('draws the radar of the percentiles of the main row with the numbers beside it (not only a picture)', async () => {
    open(ANA)
    const radar = await screen.findByRole('img', { name: /Perfil de ANA PRUEBA UNO/ })
    expect(radar).toBeInTheDocument()
    const list = screen.getByRole('list', { name: /Percentiles/ })
    expect(within(list).getAllByRole('listitem')).toHaveLength(8)
    expect(within(list).getByText(/Cuidar el balón/)).toBeInTheDocument()
  })

  it('opens only the competitions of the league of the player: a FBCYL one does not download the FEB files', async () => {
    const fbcyl = (await (async () => { setTalentBase(TALENT_BASE); return loadCompetitionRows(FBCYL_KEY) })()).rows.find(r => !r.linked_to)!
    resetTalentData(); host.requested.length = 0
    open(fbcyl.person_id)
    await screen.findByRole('heading', { level: 1 })
    expect(host.requested.some(f => f.includes('players/'))).toBe(true)
    const manifest = JSON.parse(readTalent('index.json'))
    const lf2 = manifest.competitions.find((c: { key: string }) => c.key === LF2_KEY)
    expect(host.requested).not.toContain(lf2.file)
  })

  it('says «no data» for what a FBCYL player does not have (no bio) and never a zero', async () => {
    const fbcyl = (await loadCompetitionRows(FBCYL_KEY)).rows.find(r => !r.linked_to)!
    resetTalentData()
    open(fbcyl.person_id)
    expect(await screen.findByText(/Altura/)).toBeInTheDocument()
    expect(screen.getAllByTitle('Sin dato').length).toBeGreaterThan(0)
  })

  it('offers the other rows of the player for the radar and changes it when one is chosen', async () => {
    const manifest = JSON.parse(readTalent('index.json'))
    const lf2 = manifest.competitions.find((c: { key: string }) => c.key === LF2_KEY)
    manifest.competitions.push({ ...lf2, key: 'feb|lf2|2024', season: '2024', season_label: '2024/2025' })
    host.override['index.json'] = JSON.stringify(manifest)
    open(ANA)
    await screen.findByRole('img', { name: /Perfil de ANA PRUEBA UNO/ })
    const choose = screen.getByRole('combobox', { name: /Perfil de/i })
    expect(within(choose).getAllByRole('option').length).toBeGreaterThanOrEqual(2)
    const options = within(choose).getAllByRole('option')
    const other = options[options.length - 1]
    expect(choose).not.toHaveValue((other as HTMLOptionElement).value)                    // it starts on the latest season
    await userEvent.selectOptions(choose, other)
    await waitFor(() => expect(choose).toHaveValue((other as HTMLOptionElement).value))
    expect(screen.getByRole('img', { name: /Perfil de ANA PRUEBA UNO/ })).toBeInTheDocument()
  })

  it('puts the FBCYL trajectory of a linked player in the profile of the FEB person, marked as coming from there (#996)', async () => {
    open(ANA)
    const trajectory = (await screen.findByRole('heading', { name: /Trayectoria/ })).closest('section')!
    expect(await within(trajectory).findByText(/Primera Nacional Femenina/)).toBeInTheDocument()
    expect(within(trajectory).getByText(/L\.F\.-2/)).toBeInTheDocument()
    expect(within(trajectory).getByText('Enlazada de FBCYL')).toBeInTheDocument()
    expect(within(trajectory).getAllByText(/2026/).length).toBeGreaterThan(0)
  })

  it('sends the profile of a linked FBCYL player to the one of her FEB person, and opens the FBCYL files only for who has them linked', async () => {
    const linked = (await loadCompetitionRows(FBCYL_KEY)).rows.find(r => r.linked_to)!
    resetTalentData()
    open(linked.person_id)
    expect(await screen.findByRole('heading', { level: 1, name: /ANA PRUEBA UNO/ })).toBeInTheDocument()
    expect((await screen.findAllByText(/Primera Nacional Femenina/)).length).toBeGreaterThan(0)
    resetTalentData(); host.requested.length = 0
    open('feb:10200')
    await screen.findByRole('heading', { level: 1, name: /BEA PRUEBA DOS/ })
    const manifest = JSON.parse(readTalent('index.json'))
    expect(host.requested).not.toContain(manifest.competitions.find((c: { key: string }) => c.key === FBCYL_KEY).file)
  })

  it('says it when nobody has that id, and offers the way back to the search', async () => {
    open('feb:no-existe')
    expect(await screen.findByText(/No encontramos a este jugador/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Volver al buscador/ })).toHaveAttribute('href', '/')
  })

  it('says it when the publication is not there yet', async () => {
    host.override['index.json'] = null
    open(ANA)
    expect(await screen.findByText(/Aún no hay datos de jugadores publicados/)).toBeInTheDocument()
  })
})
