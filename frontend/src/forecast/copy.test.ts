import { describe, expect, it } from 'vitest'
import { FACTOR_NAMES, SCENARIO_TEXT, confidenceText, highlightText, leverDetail, leverEvidence, leverTitle, pct } from './copy'
import { buildGames } from './gameLog'
import { buildModel } from './pool'
import { bucketsOf, evaluate } from './scenarios'
import { leversOf, type Lever } from './levers'
import { lfChallenge, lfChallengeCalendar, primera } from '@/test/forecastFixtures'

// What the page says. The study of 26/10/2026 found no evidence that correcting a factor during a game changes what follows, so an objective is only ever «in the games where this happens, we win this
// often»: nothing here promises that making it happen wins, and nothing says «+N % de victoria». The wording is neutral in gender («el rival», «nuestro»).
const lever = (over: Partial<Lever>): Lever => ({ side: 'defence', factor: 'orb', direction: 'down', threshold: 0.28, expected: 0.31, pWin: 0.46, gain: 0.08, mass: 0.25, record: { reached: 7, won: 5 }, ...over })

describe('the objectives, in the words of the page', () => {
  it('say what to do with the target, as a rule of the project (one sentence per kind)', () => {
    expect(leverTitle(lever({}))).toBe('Dejar su rebote ofensivo en ≤ 28 %')
    expect(leverTitle(lever({ side: 'attack', factor: 'efg', direction: 'up', threshold: 0.5664 }))).toBe('Subir nuestro acierto de tiro (eFG %) hasta ≥ 56,6 %')
    expect(leverTitle(lever({ side: 'attack', factor: 'tov', direction: 'down', threshold: 0.131 }))).toBe('Cuidar el balón: pérdidas ≤ 13,1 % de las posesiones')
    expect(leverTitle(lever({ side: 'attack', factor: 'orb', direction: 'up', threshold: 0.363 }))).toBe('Subir nuestro rebote ofensivo hasta ≥ 36,3 %')
    expect(leverTitle(lever({ side: 'attack', factor: 'ftr', direction: 'up', threshold: 0.384 }))).toBe('Ir más a la línea: ≥ 38 tiros libres por cada 100 tiros de campo')
    expect(leverTitle(lever({ factor: 'efg', direction: 'down', threshold: 0.465 }))).toBe('Limitar su acierto de tiro (eFG %) a ≤ 46,5 %')
    expect(leverTitle(lever({ factor: 'tov', direction: 'up', threshold: 0.163 }))).toBe('Forzar sus pérdidas: ≥ 16,3 % de sus posesiones')
    expect(leverTitle(lever({ factor: 'ftr', direction: 'down', threshold: 0.276 }))).toBe('Evitar que vayan a la línea: ≤ 28 tiros libres por cada 100 tiros de campo')
    expect(leverTitle(lever({ side: 'pace', factor: undefined, direction: 'up', threshold: 75.8 }))).toBe('Subir el ritmo: ≥ 76 posesiones por 40 minutos')
    expect(leverTitle(lever({ side: 'pace', factor: undefined, direction: 'down', threshold: 66.2 }))).toBe('Bajar el ritmo: ≤ 66 posesiones por 40 minutos')
  })

  it('say how often it happens and how often we win when it does, against how often overall', () => {
    expect(leverDetail(lever({}), 0.38)).toBe('Pasa en 1 de cada 4 partidos como este. En esos partidos ganamos el 46 % (en general, el 38 %).')
  })

  it('say how the season went when our games got there, or that they have not', () => {
    expect(leverEvidence(lever({}))).toBe('Esta temporada, cuando lo hemos logrado, ganamos 5 de 7.')
    expect(leverEvidence(lever({ record: { reached: 1, won: 1 } }))).toBe('Esta temporada, cuando lo hemos logrado, ganamos 1 de 1.')
    expect(leverEvidence(lever({ record: { reached: 0, won: 0 } }))).toBe('Esta temporada todavía no lo hemos logrado.')
  })

  it('percentages have the decimal comma and a space before the sign', () => {
    expect(pct(0.5664)).toBe('56,6 %')
    expect(pct(0.28, 0)).toBe('28 %')
    expect(pct(1)).toBe('100,0 %')
  })
})

describe('every sentence the page can say on real matchups', () => {
  const sentences: string[] = []
  for (const [f, calendar] of [[primera(), null], [lfChallenge(), lfChallengeCalendar()]] as const) {
    const model = buildModel(buildGames(f.team_rows, calendar), f.gender)
    const ids = [...new Set(model.games.flatMap(g => [g.home, g.away]))]
    for (let i = 0; i + 1 < ids.length; i += 2) {
      const ev = evaluate(model, ids[i], ids[i + 1], 'own')!
      const levers = leversOf(model, ev)
      for (const l of [...levers.attack, ...levers.defence, ...(levers.pace ? [levers.pace] : [])]) sentences.push(leverTitle(l), leverDetail(l, ev.headline.p), leverEvidence(l))
      for (const b of bucketsOf(ev)) sentences.push(...b.highlights.map(highlightText))
    }
  }

  it('there are plenty of them', () => {
    expect(sentences.length).toBeGreaterThan(100)
  })

  it('never promise anything: no «+N %», no guarantee, no cause', () => {
    for (const s of sentences) {
      expect(s).not.toMatch(/\+\s*\d[\d,.]*\s*%/)
      expect(s).not.toMatch(/garantiz|asegur|seguro|provoca|causa|hará que|hara que|si lo logramos|si logramos/i)
    }
  })

  it('are neutral in gender: no «ganador», «perdedor», «favorito», «jugador», «entrenador»', () => {
    for (const s of sentences) expect(s).not.toMatch(/ganador|perdedor|favorit|jugador|entrenador/i)
  })

  it('have no placeholder, NaN or undefined in them', () => {
    for (const s of sentences) expect(s).not.toMatch(/NaN|undefined|null|\{|\}/)
  })
})

describe('the rest of the words', () => {
  it('every kind of game and every factor has its text', () => {
    expect(Object.keys(SCENARIO_TEXT).sort()).toEqual(['lossBig', 'lossClose', 'winBig', 'winClose'])
    expect(Object.keys(FACTOR_NAMES).sort()).toEqual(['efg', 'ftr', 'orb', 'tov'])
  })

  it('a highlight says whose factor it is, what it was in this kind of game and what was expected', () => {
    expect(highlightText({ side: 'own', factor: 'efg', value: 0.551, expected: 0.513, z: 1.2 })).toBe('Nuestro acierto de tiro: 55,1 % (esperado 51,3 %)')
    expect(highlightText({ side: 'rival', factor: 'tov', value: 0.171, expected: 0.14, z: 0.9 })).toBe('Sus pérdidas: 17,1 % (esperado 14,0 %)')
  })

  it('the reasons for a low confidence are told in plain words', () => {
    expect(confidenceText({ kind: 'few-games', team: '1', name: 'ALPHA', games: 3 })).toBe('ALPHA solo ha jugado 3 partidos.')
    expect(confidenceText({ kind: 'few-games', team: '1', name: 'ALPHA', games: 1 })).toBe('ALPHA solo ha jugado 1 partido.')
    expect(confidenceText({ kind: 'few-games', team: '1', name: 'ALPHA', games: 0 })).toBe('ALPHA aún no ha jugado ningún partido.')
    expect(confidenceText({ kind: 'small-pool', size: 12 })).toBe('Hay pocos partidos de la competición para comparar (12).')
  })
})
