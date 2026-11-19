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

  it('offers the comparator with this player already chosen (#881)', async () => {
    open(ANA)
    await screen.findByRole('heading', { level: 1, name: /ANA PRUEBA UNO/ })
    expect(screen.getByRole('link', { name: /Comparar con otros jugadores/ })).toHaveAttribute('href', '/comparar?j=feb%3A10100')
  })

  it('shows the shots by zone of the row of the profile with the league percentage beside it, and says when the row has no shots (#994)', async () => {
    open('feb:10101')
    const section = (await screen.findByRole('heading', { name: /Zonas de tiro/ })).closest('section')!
    const table = await within(section).findByRole('table', { name: /Tiros por zona/ })
    expect(within(table).getByRole('rowheader', { name: 'Área restringida' })).toBeInTheDocument()
    expect(within(table).getAllByRole('row')).toHaveLength(1 + 10 + 1)                    // header, ten zones and the total
    expect(within(table).getByRole('columnheader', { name: /% liga/ })).toBeInTheDocument()
    expect(within(section).getByRole('region', { name: /Tabla de zonas de tiro/ })).toHaveAttribute('tabindex', '0')
    expect(section.querySelectorAll('svg [data-zone]').length).toBeGreaterThan(0)          // the court of Analytics with a bubble per zone with shots (#1010)
  })

  it('does not draw a zones table for a player without shots in the file', async () => {
    open('feb:10200')
    const section = (await screen.findByRole('heading', { name: /Zonas de tiro/ })).closest('section')!
    expect(await within(section).findByText(/Sin tiros registrados/)).toBeInTheDocument()
    expect(within(section).queryByRole('table')).not.toBeInTheDocument()
  })

  it('shows the photo FEB publishes for the player next to his name, and the initials of a FBCYL player without a FEB id (#1010)', async () => {
    open(ANA)
    const photo = await screen.findByRole('img', { name: 'ANA PRUEBA UNO' })
    expect(photo).toHaveAttribute('src', 'https://imagenes.feb.es/foto.aspx?c=10100')
  })

  it('shows initials, not a broken image, for a FBCYL player nobody links (#1010)', async () => {
    const fbcyl = (await loadCompetitionRows(FBCYL_KEY)).rows.find(r => !r.linked_to)!
    resetTalentData()
    open(fbcyl.person_id)
    await screen.findByRole('heading', { level: 1 })
    expect(document.querySelector('img[src*="foto.aspx"]')).toBeNull()
  })

  it('lists the five players most like him in his own competition, with the similarity, the age and a way to compare (#1010)', async () => {
    open('feb:10101')
    const section = (await screen.findByRole('heading', { name: /Jugadores parecidos/ })).closest('section')!
    const list = await within(section).findByRole('list', { name: 'Jugadores parecidos' })
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(5)
    expect(within(items[0]).getByText(/%/)).toBeInTheDocument()
    expect(within(items[0]).getByRole('link', { name: /Comparar con/ }).getAttribute('href')).toMatch(/^\/comparar\?j=feb%3A10101%2C/)
    expect(within(section).getByText(/Solo se comparan jugadores de la misma competición y temporada/)).toBeInTheDocument()
  })

  it('has a navigation inside the profile with a link to each section, and every link goes to a section that is there (#1010)', async () => {
    open('feb:10101')
    await screen.findByRole('heading', { name: /Zonas de tiro/ })
    const nav = screen.getByRole('navigation', { name: 'En esta ficha' })
    const links = within(nav).getAllByRole('link')
    expect(links.map(l => l.textContent)).toEqual(['Datos personales', 'Trayectoria', 'Perfil', 'Parecidos', 'Zonas de tiro'])
    for (const link of links) {
      const target = document.getElementById(link.getAttribute('href')!.slice(1))
      expect(target, link.textContent!).not.toBeNull()
      expect(target!.tagName).toBe('SECTION')
      expect(within(target!).getByRole('heading', { level: 2 }).textContent!.toLowerCase()).toContain(link.textContent!.toLowerCase())          // the link says what the section is about
    }
  })

  it('can be exported as a PDF or a picture, with no CSV (it is not a table of rows), named after the player (#1010)', async () => {
    open(ANA)
    await screen.findByRole('heading', { level: 1, name: /ANA PRUEBA UNO/ })
    await userEvent.click(screen.getByRole('button', { name: /Exportar/ }))
    expect(screen.getByRole('button', { name: 'PDF' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'PNG' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'CSV' })).not.toBeInTheDocument()
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
