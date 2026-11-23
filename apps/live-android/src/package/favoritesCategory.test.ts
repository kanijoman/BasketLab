// Issue #1055 (feedback of 0.7.0): a team of interest is a club IN A CATEGORY, not a name. A club has the same name in every category (senior, cadete, júnior…): the favourite of the
// senior team marked the matches of its youth teams. The id still says «the same team»; the name only says it across seasons (ids change), and only inside the same category.
import { describe, expect, it } from 'vitest'
import { filterRounds, NO_FILTERS } from './filters'
import { isFavorite, loadFavorites, teamScope, toggleFavorite, type Favorite } from './favorites'
import { orderRounds, type CompetitionInfo, type RoundIndexEntry } from './remote'
import { nextMatchesOfFavorites, nextMatchList } from './upcoming'

const info = (over: Partial<CompetitionInfo>): CompetitionInfo => ({ key: 'k', label: 'l', competition: 'c', group: 'g', season: '2026', level: null, gender: 'F', category: 'senior', age_group: null, ...over })
const SENIOR = info({ competition: 'TERCERA FEB', level: 4 })
const CADETE = info({ competition: '1ª DIV CADETE FEM', category: 'formacion', age_group: 'U16', league: 'FBCYL' })
const JUNIOR = info({ competition: '1ª DIV JUNIOR FEM', category: 'formacion', age_group: 'U18', league: 'FBCYL' })

const round = (competition: CompetitionInfo | undefined, code: string, home: { id: string; name: string }): RoundIndexEntry => ({
  competition, collection: `C_${code}`, round: 1, file: 'f', sha256: 's', bytes: 1, club: false,
  matches: [{ code, start: '2099-01-01T12:00', home, away: { id: `r${code}`, name: `RIVAL ${code}` }, own_id: home.id, is_club: false }],
})
const RDL = 'CAJA RURAL RDL'
const rounds = [round(SENIOR, 'sen', { id: '10', name: RDL }), round(CADETE, 'cad', { id: '20', name: RDL }), round(JUNIOR, 'jun', { id: '30', name: RDL })]
const ofSenior: Favorite = { teamId: '9', name: RDL, scope: teamScope(SENIOR) ?? undefined }     // the id of last season: only the name can say it is this team

function memory(initial?: string): Storage {
  const data = new Map<string, string>(initial === undefined ? [] : [['basketlab-live-favorites', initial]])
  return { getItem: k => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: k => void data.delete(k), clear: () => data.clear(), key: () => null, get length() { return data.size } }
}

describe('the category of a team', () => {
  it('senior is one category whatever the division; youth is its age group; the gender tells the branches apart', () => {
    expect(teamScope(SENIOR)).toBe(teamScope(info({ competition: 'SEGUNDA FEB', level: 3 })))
    expect(teamScope(CADETE)).not.toBe(teamScope(JUNIOR))
    expect(teamScope(SENIOR)).not.toBe(teamScope(info({ gender: 'M' })))
  })
  it('an index from before the category existed says nothing', () => {
    expect(teamScope(undefined)).toBeNull()
    expect(teamScope({ ...SENIOR, category: undefined, age_group: undefined })).toBeNull()
  })
})

describe('is it the favourite team?', () => {
  it('the same id is the same team, in any category', () => {
    expect(isFavorite([{ teamId: '20', name: 'X', scope: teamScope(SENIOR) ?? undefined }], '20', RDL, teamScope(CADETE))).toBe(true)
  })
  it('the name across seasons only counts inside the same category', () => {
    expect(isFavorite([ofSenior], '10', RDL, teamScope(SENIOR))).toBe(true)
    expect(isFavorite([ofSenior], '20', RDL, teamScope(CADETE))).toBe(false)
    expect(isFavorite([ofSenior], '30', RDL, teamScope(JUNIOR))).toBe(false)
  })
  it('a favourite saved before the category existed is read as senior: its name does not mark youth teams', () => {
    const old: Favorite = { teamId: '9', name: RDL }
    expect(isFavorite([old], '10', RDL, teamScope(SENIOR))).toBe(true)
    expect(isFavorite([old], '20', RDL, teamScope(CADETE))).toBe(false)
  })
  it('without the category of the match (an old index) the name decides, as before', () => {
    expect(isFavorite([ofSenior], '99', RDL, null)).toBe(true)
  })
})

describe('what the screens show for a club that has the same name in three categories', () => {
  it('«solo de interés» keeps the senior match only', () => {
    expect(filterRounds(rounds, { ...NO_FILTERS, onlyFavorites: true }, [ofSenior]).map(r => r.matches[0].code)).toEqual(['sen'])
  })
  it('the next match of the favourite is the senior one, and no youth match is listed as of interest', () => {
    expect(nextMatchesOfFavorites(rounds, [ofSenior], new Date('2098-01-01')).map(n => n.match.code)).toEqual(['sen'])
    expect(nextMatchList(rounds, NO_FILTERS, [ofSenior], new Date('2098-01-01')).map(u => u.match.code)).toEqual(['sen'])
  })
  it('the senior round goes first and the youth rounds are not lifted by the name', () => {
    expect(orderRounds([rounds[1], rounds[0], rounds[2]], [ofSenior]).map(r => r.matches[0].code)[0]).toBe('sen')
  })
})

describe('marking and unmarking a team', () => {
  it('the favourite remembers its category, and unmarking the senior team leaves a youth team of the same name as it was', () => {
    const s = memory()
    expect(toggleFavorite({ teamId: '10', name: RDL, scope: teamScope(SENIOR) ?? undefined }, s)).toBe(true)
    expect(toggleFavorite({ teamId: '20', name: RDL, scope: teamScope(CADETE) ?? undefined }, s)).toBe(true)           // another team: it is marked, not unmarked by the name
    expect(loadFavorites(s).map(f => f.teamId)).toEqual(['10', '20'])
    expect(loadFavorites(s)[0].scope).toBe(teamScope(SENIOR))
  })
})
