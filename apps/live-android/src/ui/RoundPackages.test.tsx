import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { RoundIndexEntry, RoundMatch } from '../package/remote'
import RoundPackages from './RoundPackages'
import { optionLabels, pickOption, valueOf } from '../test/select'

const side = (id: string, name: string) => ({ id, name })
const match = (code: string, home: [string, string], away: [string, string]): RoundMatch =>
  ({ code, start: '2026-10-17T17:00', home: side(...home), away: side(...away), own_id: home[0], own_ids: [home[0], away[0]], is_club: false })
const info = (competition: string, group: string) => ({ key: 'k', label: `${competition} · ${group}`, competition, group, season: '2026/2027', level: 3, gender: 'M' as const })
const round = (collection: string, matches: RoundMatch[], competition?: ReturnType<typeof info>): RoundIndexEntry =>
  ({ collection, round: 4, file: `rounds/${collection}.bpkgz`, sha256: 'x', bytes: 1, club: false, matches, ...(competition ? { competition } : {}) })

const ROUNDS = [
  round('SEGUNDA_FEB_A', [match('1', ['1008857', 'LEONESA'], ['2', 'ZAMORA']), match('2', ['3', 'GETAFE'], ['4', 'TOLEDO'])], info('SEGUNDA FEB', 'Liga Regular "A"')),
  round('SEGUNDA_FEB_B', [match('3', ['1008978', 'LLIRIA'], ['5', 'PRAT'])], info('SEGUNDA FEB', 'Liga Regular "B"')),
  round('TERCERA_FEB_AB', [match('4', ['1010490', 'RDL'], ['6', 'MIERES'])], info('TERCERA FEB', 'Liga Regular "A-B"')),
]

const NOW = new Date('2026-10-17T10:00:00')
const show = (rounds = ROUNDS, over: Partial<React.ComponentProps<typeof RoundPackages>> = {}) =>
  render(<RoundPackages rounds={rounds} canOpen={() => true} busy={null} onDownload={vi.fn()} isLoaded={() => false} now={NOW} {...over} />)
const rows = (c: HTMLElement) => Array.from(c.querySelectorAll('li.round-match')) as HTMLElement[]
const codes = (c: HTMLElement) => rows(c).map(li => li.getAttribute('data-code'))
const competitions = (c: HTMLElement) => rows(c).map(li => li.querySelector('.round-competition')?.textContent ?? '')

beforeEach(() => localStorage.clear())
afterEach(cleanup)

describe('RoundPackages: the list of matches to follow (issues #511, #440)', () => {
  it('lists the next match of each team with the label of its competition data, not the name of the collection', () => {
    const { container } = show()
    expect(codes(container)).toEqual(['1', '2', '3', '4'])
    expect(competitions(container)).toEqual(['SEGUNDA FEB · Liga Regular "A"', 'SEGUNDA FEB · Liga Regular "A"', 'SEGUNDA FEB · Liga Regular "B"', 'TERCERA FEB · Liga Regular "A-B"'])
  })

  it('an index without competition data keeps the old title and works', () => {
    const { container } = show([round('LF_CHALLENGE_2026_Liga', [match('9', ['1', 'ADBA'], ['2', 'ZAMORA'])])])
    expect(competitions(container)).toEqual(['LF CHALLENGE 2026 Liga'])
    expect(screen.queryByLabelText(/grupo/i)).toBeNull()
  })

  it('shows only one match for a team: its next one, not the following rounds', () => {
    const later = round('SEGUNDA_FEB_A_NEXT', [{ ...match('20', ['2', 'ZAMORA'], ['3', 'GETAFE']), start: '2026-10-24T17:00' }], info('SEGUNDA FEB', 'Liga Regular "A"'))
    const { container } = show([...ROUNDS, later])
    expect(codes(container)).not.toContain('20')
  })

  it('there is no list of complete rounds any more: no round headings', () => {
    const { container } = show()
    expect(container.querySelectorAll('.round-packages h3')).toHaveLength(0)
  })
})

describe('RoundPackages: the filters come in order and the list is under them (issue #511)', () => {
  it('has the selectors, then the list of the matches that pass them', () => {
    const { container } = show()
    const filters = screen.getByRole('group', { name: 'Filtrar partidos' })
    expect(filters.compareDocumentPosition(container.querySelector('li.round-match')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('filters by competition and then by group', () => {
    const { container } = show()
    pickOption('Competición', 'SEGUNDA FEB')
    expect(codes(container)).toEqual(['1', '2', '3'])
    pickOption('Grupo', 'Liga Regular "B"')
    expect(codes(container)).toEqual(['3'])
  })

  it('the group selector appears only once a competition with groups is chosen', () => {
    show()
    expect(screen.queryByRole('combobox', { name: 'Grupo' })).toBeNull()
    pickOption('Competición', 'TERCERA FEB')
    expect(screen.queryByRole('combobox', { name: 'Grupo' })).not.toBeNull()
  })

  it('has no free text box: the team is chosen from a list, after the competition (issue #474)', () => {
    show()
    expect(screen.queryByLabelText('Buscar equipo')).toBeNull()
    expect(screen.queryByRole('combobox', { name: 'Equipo' })).toBeNull()
  })

  it('once a competition is chosen the team selector lists its teams, and choosing one shows only its next match', () => {
    const { container } = show()
    pickOption('Competición', 'SEGUNDA FEB')
    expect(optionLabels('Equipo')).toEqual(['Todos', 'GETAFE', 'LEONESA', 'LLIRIA', 'PRAT', 'TOLEDO', 'ZAMORA'])
    pickOption('Equipo', '1008978')
    expect(codes(container)).toEqual(['3'])
  })

  it('changing the competition brings the team back to «Todos» if it is not there', () => {
    show()
    pickOption('Competición', 'SEGUNDA FEB')
    pickOption('Equipo', '1008978')
    pickOption('Competición', 'TERCERA FEB')
    expect(valueOf('Equipo')).toBe('')
  })

  it('a remembered team that is not published any more does not hide everything', () => {
    localStorage.setItem('basketlab-live-filters', JSON.stringify({ league: '', competition: 'SEGUNDA FEB', group: '', team: 'ya no está', onlyFavorites: false }))
    const { container } = show()
    expect(codes(container)).toEqual(['1', '2', '3'])
  })

  it('the league selector appears only when there are FEB and FBCYL matches, and filters by it', () => {
    show()
    expect(screen.queryByRole('combobox', { name: 'Liga' })).toBeNull()
    cleanup()
    const fbcyl = round('FBCYL_1_FASE-GRUPO_A-1_2026_', [match('77', ['39609', 'UNILEON'], ['40083', 'HIJOLUSA'])])
    const { container } = show([...ROUNDS, fbcyl])
    pickOption('Liga', 'FBCYL')
    expect(codes(container)).toEqual(['77'])
    expect(optionLabels('Competición')).toEqual(['Todas', 'FBCYL 1 FASE-GRUPO A-1 2026'])
  })

  it('says so when nothing is left to play, and the filters can be cleared', () => {
    localStorage.setItem('basketlab-live-filters', JSON.stringify({ league: '', competition: 'SEGUNDA FEB', group: '', team: '', onlyFavorites: false }))
    show(ROUNDS, { now: new Date('2026-12-01T10:00:00') })
    expect(screen.getByText(/ningún partido coincide/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /quitar filtros/i }))
    expect(valueOf('Competición')).toBe('')
  })

  it('remembers the filters on the device', () => {
    show()
    pickOption('Competición', 'TERCERA FEB')
    cleanup()
    const { container } = show()
    expect(valueOf('Competición')).toBe('TERCERA FEB')
    expect(codes(container)).toEqual(['4'])
  })

  it('a remembered competition that is not published any more does not hide everything', () => {
    localStorage.setItem('basketlab-live-filters', JSON.stringify({ league: '', competition: 'COMPETICIÓN QUE YA NO ESTÁ', group: '', team: '', onlyFavorites: false }))
    const { container } = show()
    expect(codes(container)).toHaveLength(4)
  })
})

describe('RoundPackages: teams «de interés» (issue #440)', () => {
  it('a star next to each team marks it, only on this device', () => {
    show()
    const star = screen.getByRole('button', { name: 'Marcar LEONESA como de interés' })
    fireEvent.click(star)
    expect(screen.getByRole('button', { name: 'Quitar LEONESA de los equipos de interés' })).toBeTruthy()
    expect(JSON.parse(localStorage.getItem('basketlab-live-favorites') ?? '[]')).toEqual([{ teamId: '1008857', name: 'LEONESA' }])
  })

  it('unmarks it with a second click', () => {
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Marcar LEONESA como de interés' }))
    fireEvent.click(screen.getByRole('button', { name: 'Quitar LEONESA de los equipos de interés' }))
    expect(JSON.parse(localStorage.getItem('basketlab-live-favorites') ?? '[]')).toEqual([])
  })

  it('by default, with teams of interest, only their next match is listed, and the text says so (#569)', () => {
    localStorage.setItem('basketlab-live-favorites', JSON.stringify([{ teamId: '1010490', name: 'RDL' }]))
    const { container } = show()
    expect(codes(container)).toEqual(['4'])
    expect(screen.getByText(/próximo partido de tus equipos de interés/i)).toBeTruthy()
  })

  it('once a competition is chosen the rest of its matches come after the ones with a team of interest', () => {
    localStorage.setItem('basketlab-live-favorites', JSON.stringify([{ teamId: '1008978', name: 'LLIRIA' }]))
    const { container } = show()
    pickOption('Competición', 'SEGUNDA FEB')
    expect(codes(container)).toEqual(['3', '1', '2'])
  })

  it('with nobody of interest it lists every team and asks to mark some', () => {
    const { container } = show()
    expect(codes(container)).toEqual(['1', '2', '3', '4'])
    expect(screen.getByText(/marca equipos de interés/i)).toBeTruthy()
  })

  it('a team chosen shows only its match even if it is not a team of interest', () => {
    localStorage.setItem('basketlab-live-favorites', JSON.stringify([{ teamId: '1010490', name: 'RDL' }]))
    const { container } = show()
    pickOption('Competición', 'SEGUNDA FEB')
    pickOption('Equipo', '3')
    expect(codes(container)).toEqual(['2'])
  })
})

describe('RoundPackages: how a match is followed (issues #510, #511)', () => {
  it('with no team of interest each side of the match can be followed', () => {
    const onDownload = vi.fn()
    const { container } = show(ROUNDS, { onDownload })
    const row = rows(container)[0]
    fireEvent.click(within(row).getByRole('button', { name: /descargar LEONESA contra ZAMORA como ZAMORA/i }))
    expect(onDownload).toHaveBeenCalledWith(ROUNDS[0], ROUNDS[0].matches[0], '2')
    expect(within(row).getByRole('button', { name: /descargar LEONESA contra ZAMORA como LEONESA/i })).toBeTruthy()
  })

  it('a team of interest is always the side followed, the other side is not offered', () => {
    localStorage.setItem('basketlab-live-favorites', JSON.stringify([{ teamId: '1008857', name: 'LEONESA' }]))
    const onDownload = vi.fn()
    const { container } = show(ROUNDS, { onDownload })
    const row = container.querySelector('li.round-match[data-code="1"]') as HTMLElement
    expect(within(row).queryByRole('button', { name: /como ZAMORA/i })).toBeNull()
    fireEvent.click(within(row).getByRole('button', { name: /como LEONESA/i }))
    expect(onDownload).toHaveBeenCalledWith(ROUNDS[0], ROUNDS[0].matches[0], '1008857')
  })

  it('when two teams of interest play each other, the user chooses', () => {
    localStorage.setItem('basketlab-live-favorites', JSON.stringify([{ teamId: '1008857', name: 'LEONESA' }, { teamId: '2', name: 'ZAMORA' }]))
    const { container } = show()
    const row = container.querySelector('li.round-match[data-code="1"]') as HTMLElement
    expect(within(row).getAllByRole('button').filter(b => /como/i.test(b.getAttribute('aria-label') ?? ''))).toHaveLength(2)
  })

  it('a match that cannot be opened has disabled buttons, and the one loaded says «Ya disponible»', () => {
    const { container } = show(ROUNDS, { canOpen: () => false })
    expect(Array.from(container.querySelectorAll('li.round-match .round-sides button')).every(b => (b as HTMLButtonElement).disabled)).toBe(true)
    cleanup()
    show(ROUNDS, { isLoaded: (code: string, id: string) => code === '1' && id === '2' })
    expect(screen.getByText('Ya disponible')).toBeTruthy()
  })

  it('a match that is loaded but is not the one on the Partido tab can be opened from here (issue #509)', () => {
    const onOpenLoaded = vi.fn()
    show(ROUNDS, { isLoaded: (code: string, id: string) => code === '1' && id === '2', viewing: false, onOpenLoaded })
    fireEvent.click(screen.getByRole('button', { name: /ver este partido/i }))
    expect(onOpenLoaded).toHaveBeenCalled()
  })
})

describe('RoundPackages: each team on its own line with its star (issue #473)', () => {
  it('the two teams of a match are two separate rows, each with its star and its name', () => {
    const { container } = show()
    const teams = Array.from(container.querySelector('li.round-match')!.querySelectorAll('.round-team'))
    expect(teams).toHaveLength(2)
    expect(teams.map(t => t.querySelector('.team-name')?.textContent)).toEqual(['LEONESA', 'ZAMORA'])
    expect(teams.every(t => t.querySelector('button.star'))).toBe(true)
  })

  it('the competition and the date have their own lines, the buttons come after the text and not on it (issue #507)', () => {
    const { container } = show()
    const infoBlock = container.querySelector('li.round-match .round-info')!
    expect(infoBlock.firstElementChild?.classList.contains('round-competition')).toBe(true)
    expect(infoBlock.lastElementChild?.classList.contains('round-when')).toBe(true)
    const row = container.querySelector('li.round-match')!
    expect(row.children[0].classList.contains('round-info') && row.children[1].classList.contains('round-sides')).toBe(true)
  })
})

describe('RoundPackages: the reminders of the matches of interest (issue #482)', () => {
  const FAVS = [{ teamId: '1008857', name: 'LEONESA' }, { teamId: '1008978', name: 'LLIRIA' }]
  const fake = (over: Record<string, unknown> = {}) => ({
    checkPermissions: vi.fn().mockResolvedValue({ display: 'granted' }), requestPermissions: vi.fn().mockResolvedValue({ display: 'granted' }),
    schedule: vi.fn().mockResolvedValue(undefined), cancel: vi.fn().mockResolvedValue(undefined), getPending: vi.fn().mockResolvedValue({ notifications: [] }), ...over,
  })
  const withPlugin = (plugin: ReturnType<typeof fake> | null) => ({ reminders: { load: () => Promise.resolve(plugin) } }) as Partial<React.ComponentProps<typeof RoundPackages>>

  beforeEach(() => localStorage.setItem('basketlab-live-favorites', JSON.stringify(FAVS)))

  it('say nothing when no team is of interest', () => {
    localStorage.clear()
    show()
    expect(screen.queryByRole('checkbox', { name: /avisarme/i })).toBeNull()
  })

  it('are off until the user turns them on, and the app does not ask for the permission before', async () => {
    const plugin = fake()
    show(ROUNDS, withPlugin(plugin))
    expect((screen.getByRole('checkbox', { name: /avisarme/i }) as HTMLInputElement).checked).toBe(false)
    await Promise.resolve()
    expect(plugin.requestPermissions).not.toHaveBeenCalled()
    expect(plugin.schedule).not.toHaveBeenCalled()
  })

  it('turning them on asks for the permission and schedules one reminder per match, 30 minutes before', async () => {
    const plugin = fake({ checkPermissions: vi.fn().mockResolvedValue({ display: 'prompt' }) })
    show(ROUNDS, withPlugin(plugin))
    fireEvent.click(screen.getByRole('checkbox', { name: /avisarme/i }))
    await waitFor(() => expect(plugin.schedule).toHaveBeenCalledTimes(1))
    expect(plugin.requestPermissions).toHaveBeenCalled()
    const notifications = plugin.schedule.mock.calls[0][0].notifications
    expect(notifications.map((n: { title: string }) => n.title)).toEqual(['LEONESA juega en 30 min', 'LLIRIA juega en 30 min'])
    expect(await screen.findByText(/2 avisos programados/i)).toBeTruthy()
  })

  it('the choice is kept on the device and the reminders are scheduled again when the app opens', async () => {
    const plugin = fake()
    const { unmount } = render(<RoundPackages rounds={ROUNDS} canOpen={() => true} busy={null} onDownload={vi.fn()} isLoaded={() => false} now={NOW} {...withPlugin(plugin)} />)
    fireEvent.click(screen.getByRole('checkbox', { name: /avisarme/i }))
    await waitFor(() => expect(plugin.schedule).toHaveBeenCalledTimes(1))
    unmount()
    const again = fake()
    render(<RoundPackages rounds={ROUNDS} canOpen={() => true} busy={null} onDownload={vi.fn()} isLoaded={() => false} now={NOW} {...withPlugin(again)} />)
    await waitFor(() => expect(again.schedule).toHaveBeenCalledTimes(1))
    expect((screen.getByRole('checkbox', { name: /avisarme/i }) as HTMLInputElement).checked).toBe(true)
  })

  it('the lead time can be 15, 30 or 60 minutes', async () => {
    const plugin = fake()
    show(ROUNDS, withPlugin(plugin))
    fireEvent.click(screen.getByRole('checkbox', { name: /avisarme/i }))
    await waitFor(() => expect(plugin.schedule).toHaveBeenCalledTimes(1))
    pickOption('Minutos antes', '60')
    await waitFor(() => expect(plugin.schedule).toHaveBeenCalledTimes(2))
    expect(plugin.schedule.mock.calls[1][0].notifications[0].title).toBe('LEONESA juega en 60 min')
  })

  it('turning them off cancels what was scheduled', async () => {
    const plugin = fake({ getPending: vi.fn().mockResolvedValue({ notifications: [{ id: 5, extra: { basketlab: true } }] }) })
    show(ROUNDS, withPlugin(plugin))
    fireEvent.click(screen.getByRole('checkbox', { name: /avisarme/i }))
    await waitFor(() => expect(plugin.schedule).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('checkbox', { name: /avisarme/i }))
    await waitFor(() => expect(plugin.cancel).toHaveBeenCalledTimes(2))
  })

  it('says what to do when the system has the notifications denied', async () => {
    const plugin = fake({ checkPermissions: vi.fn().mockResolvedValue({ display: 'denied' }) })
    show(ROUNDS, withPlugin(plugin))
    fireEvent.click(screen.getByRole('checkbox', { name: /avisarme/i }))
    expect(await screen.findByText(/notificaciones desactivadas/i)).toBeTruthy()
    expect(plugin.schedule).not.toHaveBeenCalled()
  })

  it('says it is only in the installed app when the device cannot (a browser)', async () => {
    show(ROUNDS, withPlugin(null))
    fireEvent.click(screen.getByRole('checkbox', { name: /avisarme/i }))
    expect(await screen.findByText(/solo funcionan en la app instalada/i)).toBeTruthy()
  })
})
