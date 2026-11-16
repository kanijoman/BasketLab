import { describe, expect, it } from 'vitest'
import {
  FACTOR_NAMES, SCENARIO_TEXT, conditionText, conditionsTitle, confidenceText, highlightText, infoLines, leverDetail, leverEvidence, leverTitle, pct, pointsLine, profileValue, projectionLines,
  recordLines,
} from './copy'
import { buildGames } from './gameLog'
import { buildModel } from './pool'
import { bucketsOf, evaluate } from './scenarios'
import { leversOf, type Lever } from './levers'
import { buildProjection } from './projection/build'
import { project, type ProjectionResult, type SeasonRecord } from './projection/project'
import { fromInput, suggestedInput } from './projection/query'
import type { Condition } from './projection/variables'
import { lfChallenge, lfChallengeCalendar, primera } from '@/test/forecastFixtures'

// What the page says. The study of 26/10/2026 found no evidence that correcting a factor during a game changes what follows, so an objective is only ever «in the games where this happens, we win this
// often»: nothing here promises that making it happen wins, and nothing says «+N % de victoria». The wording is neutral in gender («el rival», «nuestro»).
const lever = (over: Partial<Lever>): Lever => ({ side: 'defence', factor: 'orb', variable: 'rival.orb', direction: 'down', threshold: 0.28, expected: 0.31, pWin: 0.46, gain: 0.08, mass: 0.25, record: { reached: 7, won: 5 }, ...over })

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
  })

  it('the pace is told as information: what is expected, how the season went at a slow and at a fast pace, and that nothing says it changes the result', () => {
    const lines = infoLines({ variable: 'game.possessions', expected: 73.8, low: { threshold: 70.2, record: { reached: 7, won: 3 } }, high: { threshold: 77.9, record: { reached: 6, won: 4 } } })
    expect(lines.title).toBe('Ritmo (informativo)')
    expect(lines.summary).toBe('Se espera un partido de unas 74 posesiones por 40 minutos.')
    expect(lines.record).toBe('Esta temporada, a ritmo lento (≤ 70 posesiones) ganamos 3 de 7 y a ritmo alto (≥ 78) ganamos 4 de 6.')
    expect(lines.caveat).toBe('Es solo una referencia: no se ha podido comprobar que el ritmo cambie la probabilidad de ganar.')
  })

  it('a pace the season has not been played at is said so', () => {
    const lines = infoLines({ variable: 'game.possessions', expected: 70, low: { threshold: 66, record: { reached: 0, won: 0 } }, high: { threshold: 74, record: { reached: 2, won: 1 } } })
    expect(lines.record).toBe('Esta temporada aún no hemos jugado a ritmo lento (≤ 66 posesiones) y a ritmo alto (≥ 74) ganamos 1 de 2.')
    expect(infoLines({ variable: 'game.possessions', expected: 70, low: { threshold: 66, record: { reached: 0, won: 0 } }, high: { threshold: 74, record: { reached: 0, won: 0 } } }).record)
      .toBe('Esta temporada aún no hemos jugado a ritmo lento (≤ 66 posesiones) ni a ritmo alto (≥ 74).')
  })

  it('our turnovers are told as information too (#941): what is expected, the season with few and with many, and that knowing them did not sharpen the probability', () => {
    const lines = infoLines({ variable: 'own.tov', expected: 0.212, low: { threshold: 0.184, record: { reached: 7, won: 5 } }, high: { threshold: 0.24, record: { reached: 0, won: 0 } } })
    expect(lines.title).toBe('Nuestras pérdidas (informativo)')
    expect(lines.summary).toBe('Lo esperado en este partido: 21,2 % de nuestras posesiones.')
    expect(lines.record).toBe('Esta temporada, con ≤ 18,4 %: ganamos 5 de 7; con ≥ 24,0 %: ninguno todavía.')
    expect(lines.caveat).toBe('Es solo una referencia: en la evaluación, conocer nuestras pérdidas no ha afinado la probabilidad de ganar.')
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

describe('the card «¿Y si…?», in the words of the page (#940)', () => {
  const c = (variable: Condition['variable'], op: Condition['op'], value: number): Condition => ({ variable, op, value })
  const record = (reached: number, won: number, scores: [number, number][] = []): SeasonRecord => ({ reached, won, scores })
  const result = (over: Partial<ProjectionResult>): ProjectionResult => ({
    conditions: [c('own.points', 'gt', 70)], mass: 0.33, pWin: 0.8, figure: 0.8, rare: false, supported: true, profile: [],
    points: { own: { expected: 66, given: 76, pace: 0, efficiency: 10 }, rival: { expected: 67, given: 67, pace: 0, efficiency: 0 } }, record: record(0, 0), rivalRecord: record(0, 0), ...over,
  })

  it('a condition says the variable, «más de» or «menos de», and the value as the page writes it', () => {
    expect(conditionText(c('own.points', 'gt', 70))).toBe('Nuestros puntos: más de 70')
    expect(conditionText(c('rival.efg', 'lt', 0.4))).toBe('Su acierto de tiro (eFG): menos del 40 %')
    expect(conditionText(c('own.tov', 'lt', 0.185))).toBe('Nuestras pérdidas: menos del 18,5 %')
    expect(conditionText(c('game.possessions', 'gt', 78.5))).toBe('Posesiones: más de 78,5')
    expect(conditionText(c('own.ftr', 'gt', 0.3))).toBe('Nuestros tiros libres por cada 100 tiros de campo: más de 30')
    expect(conditionText(c('rival.oer', 'lt', 95.5))).toBe('Sus puntos por 100 posesiones: menos de 95,5')
  })

  it('several conditions are one question: joined with «y»', () => {
    const [a, b, d] = [c('own.points', 'gt', 70), c('rival.efg', 'lt', 0.4), c('game.possessions', 'gt', 80)]
    expect(conditionsTitle([a])).toBe('Nuestros puntos: más de 70')
    expect(conditionsTitle([a, b])).toBe('Nuestros puntos: más de 70 y Su acierto de tiro (eFG): menos del 40 %')
    expect(conditionsTitle([a, b, d])).toBe('Nuestros puntos: más de 70, Su acierto de tiro (eFG): menos del 40 % y Posesiones: más de 80')
  })

  it('how often it happens and how often we win then, against how often overall', () => {
    expect(projectionLines(result({}), 0.479)).toEqual({ badge: '80 % de victorias', summary: 'Pasa en 33 de cada 100 partidos como este. En esos partidos ganamos el 80 % (en general, el 48 %).', caveat: null })
    expect(projectionLines(result({ mass: 0.998, pWin: 0.48, figure: 0.48 }), 0.479).summary).toBe('Pasa en prácticamente todos los partidos como este. En esos partidos ganamos el 48 % (en general, el 48 %).')
  })

  it('too rare for a figure, or never: said so, with no percentage of victories', () => {
    expect(projectionLines(result({ mass: 0.03, figure: null, rare: true }), 0.479))
      .toEqual({ badge: null, summary: 'Pasa en menos de 5 de cada 100 partidos como este: son muy pocos para dar una cifra.', caveat: null })
    expect(projectionLines(result({ mass: 0, pWin: NaN, figure: null, rare: true }), 0.479).summary).toBe('No pasa en ninguno de los partidos como este.')
  })

  it('without the support of the evaluation: how often, no figure, and for what', () => {
    const r = result({ conditions: [c('own.tov', 'lt', 0.18), c('own.efg', 'gt', 0.45), c('game.possessions', 'gt', 78)], mass: 0.2, figure: null, supported: false })
    expect(projectionLines(r, 0.479)).toEqual({
      badge: null, summary: 'Pasa en 20 de cada 100 partidos como este.',
      caveat: 'No damos cifra de victorias: la evaluación no la ha respaldado para nuestras pérdidas y las posesiones. Es solo una referencia.',
    })
  })

  it('the season of both teams: ours, and the rival in the same situation with its opponent in our place; the scores when they are few', () => {
    const lines = (own: SeasonRecord, rival: SeasonRecord) => recordLines(result({ record: own, rivalRecord: rival }), 'Lima-Horta')
    expect(lines(record(3, 2, [[75, 68], [72, 70], [71, 79]]), record(1, 0, [[64, 73]]))).toEqual({
      own: 'Esta temporada, nuestros partidos así: 3, y ganamos 2 (75-68, 72-70 y 71-79).',
      rival: 'Esta temporada, los de Lima-Horta en la misma situación (con su rival en nuestro lugar): 1, y no lo ganó (64-73).',
    })
    expect(lines(record(1, 1, [[80, 70]]), record(4, 3, [[1, 0], [1, 0], [1, 0], [0, 1]]))).toEqual({
      own: 'Esta temporada, nuestros partidos así: 1, y lo ganamos (80-70).',
      rival: 'Esta temporada, los de Lima-Horta en la misma situación (con su rival en nuestro lugar): 4, y ganó 3.',
    })
    expect(lines(record(5, 0), record(0, 0))).toEqual({
      own: 'Esta temporada, nuestros partidos así: 5, y no ganamos ninguno.',
      rival: 'Esta temporada, los de Lima-Horta en la misma situación (con su rival en nuestro lugar): ninguno todavía.',
    })
    expect(lines(record(0, 0), record(2, 0, [[60, 61], [70, 70]])).own).toBe('Esta temporada, nuestros partidos así: ninguno todavía.')
    expect(lines(record(1, 0, [[70, 70]]), record(2, 0, [[60, 61], [70, 70]])).rival).toBe('Esta temporada, los de Lima-Horta en la misma situación (con su rival en nuestro lugar): 2, y no ganó ninguno (60-61 y 70-70).')
  })

  it('where the points of more or of less come from: the pace and the efficiency', () => {
    // the parts to one decimal, so that they add up to the change (67 → 69 is not «+1 and +0»)
    expect(pointsLine('own', { expected: 66.2, given: 76.4, pace: 0.4, efficiency: 9.8 })).toBe('Nuestros puntos pasan de 66 a 76: ≈ +0,4 por el ritmo y ≈ +9,8 por la eficiencia (puntos por posesión).')
    expect(pointsLine('rival', { expected: 70, given: 64, pace: -4.2, efficiency: -1.8 })).toBe('Sus puntos pasan de 70 a 64: ≈ −4,2 por el ritmo y ≈ −1,8 por la eficiencia (puntos por posesión).')
    expect(pointsLine('rival', { expected: 66.6, given: 68.6, pace: 1.44, efficiency: -0.04 })).toBe('Sus puntos pasan de 67 a 69: ≈ +1,4 por el ritmo y ≈ +0,0 por la eficiencia (puntos por posesión).')
    expect(pointsLine('rival', { expected: 67, given: 67.3, pace: 0.1, efficiency: 0.2 })).toBe('Sus puntos se quedan en 67.')
  })

  it('the values of the table: the points whole, the possessions and the points per 100 to one decimal, the shares with their sign; a dash when there is none', () => {
    expect(profileValue('own.points', 76.4)).toBe('76')
    expect(profileValue('game.possessions', 75.43)).toBe('75,4')
    expect(profileValue('own.efg', 0.4667)).toBe('46,7 %')
    expect(profileValue('own.oer', 88.04)).toBe('88,0')
    expect(profileValue('rival.ftr', 0.312)).toBe('31,2')
    expect(profileValue('rival.points', NaN)).toBe('—')
  })
})

describe('every sentence the page can say on real matchups', () => {
  const sentences: string[] = []
  for (const [f, calendar] of [[primera(), null], [lfChallenge(), lfChallengeCalendar()]] as const) {
    const model = buildModel(buildGames(f.team_rows, calendar), f.gender)
    const ids = [...new Set(model.games.flatMap(g => [g.home, g.away]))]
    for (let i = 0; i + 1 < ids.length; i += 2) {
      const ev = evaluate(model, ids[i], ids[i + 1], 'own')!
      const p = buildProjection(model, ids[i], ids[i + 1], 'own')!
      const levers = leversOf(p, ev)
      for (const l of [...levers.attack, ...levers.defence]) sentences.push(leverTitle(l), leverDetail(l, ev.headline.p), leverEvidence(l))
      for (const info of levers.info) sentences.push(...Object.values(infoLines(info)).filter((s): s is string => Boolean(s)))
      for (const b of bucketsOf(ev)) sentences.push(...b.highlights.map(highlightText))
      // the card «¿Y si…?»: a question per kind of variable, alone and together
      const asked: Condition[][] = [[fromInput('own.points', 'gt', suggestedInput(p, 'own.points'))], [fromInput('rival.efg', 'lt', suggestedInput(p, 'rival.efg') - 3)],
        [fromInput('game.possessions', 'gt', suggestedInput(p, 'game.possessions') + 2)], [fromInput('own.tov', 'lt', 15), fromInput('own.points', 'gt', 90)]]
      for (const conditions of asked) {
        const r = project(p, conditions)
        const lines = projectionLines(r, ev.headline.p)
        sentences.push(conditionsTitle(conditions), lines.summary, ...[lines.badge, lines.caveat].filter((s): s is string => s !== null), ...Object.values(recordLines(r, 'el rival')))
        if (r.mass > 0) sentences.push(pointsLine('own', r.points.own), pointsLine('rival', r.points.rival))
      }
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
