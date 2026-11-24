import { describe, expect, it } from 'vitest'
import { hasLeftTeam, missedNote, missedStreak, staffNotes, type TeamGame } from './playerAvailability'

const game = (id: number, day: string): TeamGame => ({ match_id: id, starttime: `${day} - 18:00` })
const SEASON = [game(1, '04-10-2026'), game(2, '11-10-2026'), game(3, '18-10-2026'), game(4, '25-10-2026'), game(5, '01-11-2026')]
const played = (...ids: Array<number | string>) => new Set<number | string>(ids)

describe('missedStreak: the games in a row he has not played, counted back from the last game of his team', () => {
  it('counts the latest consecutive games without minutes and dates it by the first of them', () => {
    expect(missedStreak(SEASON, played(1, 2), null)).toEqual({ since: '18-10-2026', games: 3 })
  })
  it('is nothing when he played the last game', () => {
    expect(missedStreak(SEASON, played(1, 5), null)).toBeNull()
  })
  it('does not count the games before the alta: a signing who has not debuted counts from his alta (a replacement for an injured player)', () => {
    expect(missedStreak(SEASON, played(), '2026-10-20')).toEqual({ since: '25-10-2026', games: 2 })
  })
  it('counts the game of the very day of the alta', () => {
    expect(missedStreak(SEASON, played(), '2026-10-25')).toEqual({ since: '25-10-2026', games: 2 })
  })
  it('is nothing when the alta is after the last game: he has not had a game to miss', () => {
    expect(missedStreak(SEASON, played(1), '2026-11-05')).toBeNull()
  })
  it('stops at the last game he played whatever he missed before (not on the box with 0 minutes or not on it at all is the same: no row)', () => {
    expect(missedStreak(SEASON, played(1, 3), null)).toEqual({ since: '25-10-2026', games: 2 })
  })
  it('does not depend on the order of the rows and ignores a game without a readable date', () => {
    const shuffled = [SEASON[4], { match_id: 9, starttime: null }, SEASON[0], SEASON[3], SEASON[2], SEASON[1]]
    expect(missedStreak(shuffled, played(1, 2), null)).toEqual({ since: '18-10-2026', games: 3 })
  })
  it('is nothing for a team without games', () => {
    expect(missedStreak([], played(), null)).toBeNull()
  })
  it('accepts a game id as a number or as text', () => {
    expect(missedStreak(SEASON, played('1', '2', '3', '4'), null)).toEqual({ since: '01-11-2026', games: 1 })
  })
})

describe('missedNote: the sentence the technical staff reads', () => {
  it('says the date and the number of games', () => {
    expect(missedNote('A. UNO', { since: '18-10-2026', games: 3 })).toBe('A. UNO llega desde 18-10-2026 sin jugar (3 partidos)')
  })
  it('says one game in the singular', () => {
    expect(missedNote('A. UNO', { since: '01-11-2026', games: 1 })).toBe('A. UNO llega desde 01-11-2026 sin jugar (1 partido)')
  })
})

describe('hasLeftTeam: a baja already reached', () => {
  const NOW = new Date(Date.UTC(2026, 10, 24))
  it.each([
    ['2026-10-15', true], ['2026-11-24', true], ['2026-11-25', false], [null, false], [undefined, false],
  ])('baja %s -> %s', (baja, expected) => {
    expect(hasLeftTeam({ baja } as { baja?: string | null }, NOW)).toBe(expected)
  })
  it('keeps a player the publication knows nothing of', () => {
    expect(hasLeftTeam(undefined, NOW)).toBe(false)
  })
})

describe('staffNotes: the roster of a team against its published rows', () => {
  const teamRows = [...SEASON.map(g => ({ ...g, team_id: '7' })), { ...game(1, '04-10-2026'), team_id: '8' }]       // a game of another team is not his
  const rows = [{ match_id: 1, player_id: 'a', team_id: '7' }, { match_id: 2, player_id: 'a', team_id: '7' }, { match_id: 1, player_id: 'b', team_id: '7' },
    { match_id: 5, player_id: 'c', team_id: '7' }, { match_id: 3, player_id: 'a', team_id: '8' }]                      // a played in another team in 3: not here
  const roster = [{ player_id: 'a', player_name: 'A. UNO' }, { player_id: 'b', player_name: 'B. DOS' }, { player_id: 'c', player_name: 'C. TRES' }, { player_id: 'd', player_name: 'D. NUEVO' }]
  const images = { players: { d: { alta: '2026-10-25' } } }

  it('writes one sentence for each player who comes without playing and none for who played the last game', () => {
    expect(staffNotes(roster, '7', teamRows, rows, images)).toEqual({
      a: 'A. UNO llega desde 18-10-2026 sin jugar (3 partidos)',
      b: 'B. DOS llega desde 11-10-2026 sin jugar (4 partidos)',
      d: 'D. NUEVO llega desde 25-10-2026 sin jugar (2 partidos)',          // a signing: only the games since his alta
    })
  })
  it('without the images there is no alta: every game counts', () => {
    expect(staffNotes([roster[3]], '7', teamRows, rows, null)).toEqual({ d: 'D. NUEVO llega desde 04-10-2026 sin jugar (5 partidos)' })
  })
})
