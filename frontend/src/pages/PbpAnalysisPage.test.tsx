import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const NAME = 'MIPELLETYMAS B.F. LEON CON UN NOMBRE MUY LARGO'

const hooks = vi.hoisted(() => ({
  usePointsByOrigin: vi.fn(),
  useByPeriod: vi.fn(),
  useSituations: vi.fn(),
  useTimeoutEffects: vi.fn(),
}))
vi.mock('@/api/pbpExtended', () => hooks)

const ctx = vi.hoisted(() => ({ value: { collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } as unknown } }))
vi.mock('@/context/CollectionContext', () => ({ useCollection: () => ctx.value }))

import PbpAnalysisPage from './PbpAnalysisPage'

const ok = (data: unknown[]) => ({ data, isLoading: false, isError: false, error: null })

const ORIGIN = {
  team_id: '1', team_name: NAME, games: 3, games_unreliable: 1, games_paint: 3,
  pts_off_tov_per_game: 14, oer_off_tov: 105, pts_off_steal_per_game: 8, oer_off_steal: 110, pts_second_chance_per_game: 9, oer_second_chance: 95,
  pts_bench_per_game: 25, bench_pct: 33, pts_paint_per_game: 34,
  opp_pts_off_tov_per_game: 12, opp_oer_off_tov: 99, opp_pts_off_steal_per_game: 7, opp_oer_off_steal: 100, opp_pts_second_chance_per_game: 10,
  opp_oer_second_chance: 101, opp_pts_bench_per_game: 22, opp_bench_pct: 30, opp_pts_paint_per_game: 31,
}
const figures = (pts: number) => ({
  games: 3, minutes: 30, pts, opp_pts: 50, pts_per_game: pts / 3, opp_pts_per_game: 50 / 3, poss: 30, opp_poss: 30, ortg: 100, drtg: 90,
  net_rating: 10, pace: 70, efg_pct: 50, opp_efg_pct: 45, tov_pct: 15, opp_tov_pct: 16, orb_pct: 30, drb_pct: 70, ftr: 25, opp_ftr: 20,
  fouls_per_game: 5, opp_fouls_per_game: 6,
})
const PERIOD = { team_id: '1', team_name: NAME, games: 3, games_unreliable: 1, periods: { '1': figures(60), OT: figures(9) } }
const SITUATION = {
  team_id: '1', team_name: NAME, games: 3, games_unreliable: 1,
  ato_own: { n: 6, pts: 7, ppp: 1.17 }, ato_rival: { n: 2, pts: 1, ppp: 0.5 }, first_poss: { n: 5, pts: 4, ppp: 0.8 },
  edges: {
    start: { pts: 10, opp_pts: 6, poss: 10, opp_poss: 10, tov: 2, opp_tov: 1, pts_per_game: 3.3, net_rating: 40, tov_pct: 20, opp_tov_pct: 10, vs_rest: 15 },
    end: { pts: 4, opp_pts: 8, poss: 10, opp_poss: 10, tov: 3, opp_tov: 2, pts_per_game: 1.3, net_rating: -40, tov_pct: 30, opp_tov_pct: 20, vs_rest: -65 },
    rest: { pts: 26, opp_pts: 16, poss: 20, opp_poss: 20, tov: 3, opp_tov: 4, pts_per_game: 8.7, net_rating: 25, tov_pct: 15, opp_tov_pct: 20 },
  },
}
const TIMEOUT = {
  team_id: '1', team_name: NAME,
  own: { n: 4, net_rating_before: -10, net_rating_after: 20, delta_net_rating: 30, pct_caller_improves: 75 },
  rival: { n: 0, net_rating_before: null, net_rating_after: null, delta_net_rating: null, pct_caller_improves: null },
}

function renderPage() {
  return render(<MemoryRouter><PbpAnalysisPage /></MemoryRouter>)
}

describe('PbpAnalysisPage', () => {
  beforeEach(() => {
    ctx.value = { collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }
    hooks.usePointsByOrigin.mockReset().mockReturnValue(ok([ORIGIN]))
    hooks.useByPeriod.mockReset().mockReturnValue(ok([PERIOD]))
    hooks.useSituations.mockReset().mockReturnValue(ok([SITUATION]))
    hooks.useTimeoutEffects.mockReset().mockReturnValue(ok([TIMEOUT]))
  })

  it('opens on the points by origin with the full team name, the games left out and the explanation of the figures', async () => {
    renderPage()

    expect((await screen.findByText(NAME)).getAttribute('title')).toBe(NAME)
    expect(screen.getByText('Excl.')).toBeTruthy()
    expect(screen.getByText(/definición por posesión/i)).toBeTruthy()
    expect(screen.getByText('Tras pérdida')).toBeTruthy()
  })

  it('switches the origins to what the rivals score against the team', () => {
    renderPage()
    expect(screen.getByRole('button', { name: 'Propios' }).getAttribute('aria-pressed')).toBe('true')

    fireEvent.click(screen.getByRole('button', { name: 'Concedidos (rival)' }))

    expect(screen.getByRole('button', { name: 'Concedidos (rival)' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText('31.0')).toBeTruthy()          // opp_pts_paint_per_game
  })

  it('shows the period figures and lets the user pick the quarter; the overtime only lists the teams that played one', () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Por cuarto' }))

    expect(screen.getByText('20.0')).toBeTruthy()          // 60 points over 3 games in Q1
    fireEvent.click(screen.getByRole('button', { name: 'Prórroga' }))
    expect(screen.getByText('3.0')).toBeTruthy()           // 9 points over 3 games
    fireEvent.click(screen.getByRole('button', { name: 'Q3' }))
    expect(screen.getByText(/ningún equipo/i)).toBeTruthy()
  })

  it('shows the situations and the timeouts', () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Situaciones' }))
    expect(screen.getByText('Tras su tiempo muerto')).toBeTruthy()
    expect(screen.getByText('Primeros 2:00')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Tiempos muertos' }))
    expect(screen.getByText('Pedidos por el rival')).toBeTruthy()
    expect(screen.getByText('75%')).toBeTruthy()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)       // the rival group has no analysable timeouts
  })

  it('explains an empty collection: only FEB games with the backfilled DERIVED field have these figures', () => {
    hooks.usePointsByOrigin.mockReturnValue(ok([]))
    renderPage()

    expect(screen.getByText(/Sin datos del play-by-play/i)).toBeTruthy()
    expect(screen.getByText(/run_backfill_derived/)).toBeTruthy()
  })

  it('shows the error of the API', () => {
    hooks.usePointsByOrigin.mockReturnValue({ data: undefined, isLoading: false, isError: true, error: new Error('Base de datos no disponible') })
    renderPage()

    expect(screen.getByText(/Base de datos no disponible/)).toBeTruthy()
  })

  it('is FEB only: a FBCYL collection says so and asks for nothing', () => {
    ctx.value = { collection: { name: 'FBCYL_X', label: 'FBCYL X', isFbcyl: true } }
    renderPage()

    expect(screen.getByText(/solo está disponible para FEB/i)).toBeTruthy()
    expect(hooks.usePointsByOrigin).toHaveBeenCalledWith(undefined)
  })
})
