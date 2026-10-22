import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { RoundIndexEntry, RoundMatch } from '../package/remote'
import RoundPackages from './RoundPackages'

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
const headings = (c: HTMLElement) => Array.from(c.querySelectorAll('.round-packages h3')).map(h => h.textContent ?? '')

beforeEach(() => localStorage.clear())
afterEach(cleanup)

describe('RoundPackages: labels from the index (issue #440)', () => {
  it('titles each round with the label of its competition data, not with the name of the collection', () => {
    const { container } = show()
    expect(headings(container)).toEqual(['SEGUNDA FEB · Liga Regular "A" · jornada 4', 'SEGUNDA FEB · Liga Regular "B" · jornada 4', 'TERCERA FEB · Liga Regular "A-B" · jornada 4'])
  })

  it('an index without competition data keeps the old title and works', () => {
    const { container } = show([round('LF_CHALLENGE_2026_Liga', [match('9', ['1', 'ADBA'], ['2', 'ZAMORA'])])])
    expect(headings(container)).toEqual(['LF CHALLENGE 2026 Liga · jornada 4'])
    expect(screen.queryByLabelText(/grupo/i)).toBeNull()
  })
})

describe('RoundPackages: filters (issue #440)', () => {
  it('filters by competition and then by group', () => {
    const { container } = show()
    fireEvent.change(screen.getByLabelText('Competición'), { target: { value: 'SEGUNDA FEB' } })
    expect(headings(container)).toHaveLength(2)
    fireEvent.change(screen.getByLabelText('Grupo'), { target: { value: 'Liga Regular "B"' } })
    expect(headings(container)).toEqual(['SEGUNDA FEB · Liga Regular "B" · jornada 4'])
  })

  it('the group selector appears only once a competition with groups is chosen', () => {
    show()
    expect(screen.queryByLabelText('Grupo')).toBeNull()
    fireEvent.change(screen.getByLabelText('Competición'), { target: { value: 'TERCERA FEB' } })
    expect(screen.queryByLabelText('Grupo')).not.toBeNull()
  })

  it('has no free text box any more: the team is chosen from a list (issue #474)', () => {
    show()
    expect(screen.queryByLabelText('Buscar equipo')).toBeNull()
    expect(screen.queryByLabelText('Equipo')).toBeNull()          // not before a competition is chosen
  })

  it('once a competition is chosen the team selector lists its teams, and choosing one keeps its matches', () => {
    const { container } = show()
    fireEvent.change(screen.getByLabelText('Competición'), { target: { value: 'SEGUNDA FEB' } })
    const team = screen.getByLabelText('Equipo') as HTMLSelectElement
    expect(Array.from(team.options).map(o => o.textContent)).toEqual(['Todos', 'GETAFE', 'LEONESA', 'LLIRIA', 'PRAT', 'TOLEDO', 'ZAMORA'])
    fireEvent.change(team, { target: { value: '1008978' } })
    expect(headings(container)).toEqual(['SEGUNDA FEB · Liga Regular "B" · jornada 4'])
    expect(container.querySelectorAll('li.round-match')).toHaveLength(1)
  })

  it('changing the group or the competition brings the team back to «Todos» if it is not there', () => {
    show()
    fireEvent.change(screen.getByLabelText('Competición'), { target: { value: 'SEGUNDA FEB' } })
    fireEvent.change(screen.getByLabelText('Equipo'), { target: { value: '1008978' } })
    fireEvent.change(screen.getByLabelText('Competición'), { target: { value: 'TERCERA FEB' } })
    expect((screen.getByLabelText('Equipo') as HTMLSelectElement).value).toBe('')
  })

  it('a remembered team that is not published any more does not hide everything', () => {
    localStorage.setItem('basketlab-live-filters', JSON.stringify({ league: '', competition: 'SEGUNDA FEB', group: '', team: 'ya no está', onlyFavorites: false }))
    const { container } = show()
    expect(headings(container)).toHaveLength(2)
  })

  it('the league selector appears only when there are FEB and FBCYL matches, and filters by it', () => {
    show()
    expect(screen.queryByLabelText('Liga')).toBeNull()
    cleanup()
    const fbcyl = round('FBCYL_1_FASE-GRUPO_A-1_2026_', [match('77', ['39609', 'UNILEON'], ['40083', 'HIJOLUSA'])])
    const { container } = show([...ROUNDS, fbcyl])
    fireEvent.change(screen.getByLabelText('Liga'), { target: { value: 'FBCYL' } })
    expect(headings(container)).toEqual(['FBCYL 1 FASE-GRUPO A-1 2026 · jornada 4'])
    expect(Array.from((screen.getByLabelText('Competición') as HTMLSelectElement).options).map(o => o.textContent)).toEqual(['Todas', 'FBCYL 1 FASE-GRUPO A-1 2026'])
  })

  it('says so when nothing matches, and the filters can be cleared', () => {
    localStorage.setItem('basketlab-live-favorites', JSON.stringify([{ teamId: '1010490', name: 'RDL' }]))       // a team of interest of another competition
    show()
    fireEvent.change(screen.getByLabelText('Competición'), { target: { value: 'SEGUNDA FEB' } })
    fireEvent.click(screen.getByRole('checkbox', { name: /de interés/i }))
    expect(screen.getByText(/ningún partido coincide/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /quitar filtros/i }))
    expect(screen.queryByText(/ningún partido coincide/i)).toBeNull()
    expect((screen.getByRole('checkbox', { name: /de interés/i }) as HTMLInputElement).checked).toBe(false)
  })

  it('remembers the filters on the device', () => {
    show()
    fireEvent.change(screen.getByLabelText('Competición'), { target: { value: 'TERCERA FEB' } })
    cleanup()
    const { container } = show()
    expect((screen.getByLabelText('Competición') as HTMLSelectElement).value).toBe('TERCERA FEB')
    expect(headings(container)).toHaveLength(1)
  })

  it('a remembered competition that is not published any more does not hide everything', () => {
    localStorage.setItem('basketlab-live-filters', JSON.stringify({ league: '', competition: 'COMPETICIÓN QUE YA NO ESTÁ', group: '', team: '', onlyFavorites: false }))
    const { container } = show()
    expect(headings(container)).toHaveLength(3)
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

  it('the competitions and matches with a team of interest come first', () => {
    localStorage.setItem('basketlab-live-favorites', JSON.stringify([{ teamId: '1010490', name: 'RDL' }]))
    const { container } = show()
    expect(headings(container)[0]).toMatch(/TERCERA FEB/)
  })

  it('the filter «de interés» keeps only their matches', () => {
    localStorage.setItem('basketlab-live-favorites', JSON.stringify([{ teamId: '1008857', name: 'LEONESA' }]))
    const { container } = show()
    fireEvent.click(screen.getByRole('checkbox', { name: /de interés/i }))
    expect(headings(container)).toHaveLength(1)
    expect(container.querySelectorAll('li.round-match')).toHaveLength(1)
  })

  it('with the filter «de interés» and no team marked it explains what to do', () => {
    show()
    fireEvent.click(screen.getByRole('checkbox', { name: /de interés/i }))
    expect(screen.getByText(/marca con la estrella/i)).toBeTruthy()
  })

  it('the stars do not break following a match as one of its teams', () => {
    const onDownload = vi.fn()
    const { container } = render(<RoundPackages rounds={ROUNDS} canOpen={() => true} busy={null} onDownload={onDownload} isLoaded={() => false} />)
    const row = container.querySelector('li.round-match') as HTMLElement
    fireEvent.click(within(row).getByRole('button', { name: /descargar LEONESA contra ZAMORA como ZAMORA/i }))
    expect(onDownload).toHaveBeenCalledWith(ROUNDS[0], ROUNDS[0].matches[0], '2')
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

  it('the date has its own line below the teams, not after the second star', () => {
    const { container } = show()
    const info = container.querySelector('li.round-match .round-info')!
    expect(info.lastElementChild?.classList.contains('round-when')).toBe(true)
  })
})

describe('RoundPackages: the next match of each team of interest (issue #478)', () => {
  const FAVS = [{ teamId: '1008857', name: 'LEONESA' }, { teamId: '1008978', name: 'LLIRIA' }]

  it('says nothing when no team is marked', () => {
    show()
    expect(screen.queryByRole('region', { name: /próximos de tus equipos de interés/i })).toBeNull()
  })

  it('lists the next match of each team of interest, with its competition, before the filters', () => {
    localStorage.setItem('basketlab-live-favorites', JSON.stringify(FAVS))
    show()
    const next = screen.getByRole('region', { name: /próximos de tus equipos de interés/i })
    const rows = Array.from(next.querySelectorAll('li')).map(li => li.textContent ?? '')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toContain('LEONESA')
    expect(rows[0]).toContain('ZAMORA')
    expect(rows[0]).toContain('SEGUNDA FEB · Liga Regular "A"')
    expect(rows[1]).toContain('LLIRIA')
    expect(rows[1]).toContain('PRAT')
    expect(next.compareDocumentPosition(screen.getByRole('group', { name: 'Filtrar partidos' })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('follows the match as the team of interest', () => {
    localStorage.setItem('basketlab-live-favorites', JSON.stringify(FAVS))
    const onDownload = vi.fn()
    show(ROUNDS, { onDownload })
    fireEvent.click(screen.getByRole('button', { name: /seguir a llíria|seguir a lliria/i }))
    expect(onDownload).toHaveBeenCalledWith(ROUNDS[1], ROUNDS[1].matches[0], '1008978')
  })

  it('a team without a match to come is not listed, and a match that cannot be opened has a disabled button', () => {
    localStorage.setItem('basketlab-live-favorites', JSON.stringify([...FAVS, { teamId: '999', name: 'OTRO' }]))
    show(ROUNDS, { canOpen: () => false })
    const next = screen.getByRole('region', { name: /próximos de tus equipos de interés/i })
    expect(next.querySelectorAll('li')).toHaveLength(2)
    expect(Array.from(next.querySelectorAll('button')).every(b => (b as HTMLButtonElement).disabled)).toBe(true)
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
    fireEvent.change(screen.getByLabelText(/minutos antes/i), { target: { value: '60' } })
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
