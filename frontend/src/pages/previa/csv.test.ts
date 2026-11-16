import { describe, expect, it } from 'vitest'
import { conditionsTitle, infoLines, leverTitle, pct, recordLines, SCENARIO_TEXT } from '@/forecast/copy'
import { buildGames } from '@/forecast/gameLog'
import { buildModel } from '@/forecast/pool'
import { buildPreview } from '@/forecast/preview'
import { project } from '@/forecast/projection/project'
import { lfChallenge, lfChallengeCalendar } from '@/test/forecastFixtures'
import { previewCsv } from './csv'

// What the export of the preview writes to its CSV (#849, #940), on the REAL LF Challenge: the objectives, what is information, the question of the card «¿Y si…?» and the scenarios.
const f = lfChallenge()
const model = buildModel(buildGames(f.team_rows, lfChallengeCalendar()), f.gender)
const ids = [...new Set(model.games.flatMap(g => [g.home, g.away]))]
const detail = buildPreview(model, ids[0], ids[1], 'own').detail!

describe('the CSV of the preview', () => {
  it('has the objectives, what is information, the question of the card and the scenarios, in that order', () => {
    const question = project(detail.projection, [{ variable: 'own.points', op: 'gt', value: 70 }])
    const rows = previewCsv(detail, question, 'RIVAL')
    const objectives = [...detail.levers.attack, ...detail.levers.defence]
    expect(rows.map(r => r.tipo)).toEqual([...objectives.map(() => 'Objetivo'), ...detail.levers.info.map(i => infoLines(i).title), 'Condición', ...detail.scenarios.map(() => 'Escenario')])
    expect(rows.slice(0, objectives.length).map(r => r.texto)).toEqual(objectives.map(leverTitle))
    const lines = recordLines(question, 'RIVAL')
    expect(rows.find(r => r.tipo === 'Condición')).toEqual({ tipo: 'Condición', texto: conditionsTitle(question.conditions), victorias: pct(question.figure!, 0), temporada: `${lines.own} ${lines.rival}` })
    expect(rows.slice(-4).map(r => r.texto)).toEqual(detail.scenarios.map(b => SCENARIO_TEXT[b.id].title))
  })

  it('a question without a figure leaves the victories empty, and without a question there is no row for it', () => {
    const unbacked = project(detail.projection, [{ variable: 'own.tov', op: 'lt', value: 0.18 }])
    expect(previewCsv(detail, unbacked, 'RIVAL').find(r => r.tipo === 'Condición')!.victorias).toBe('')
    expect(previewCsv(detail, null, 'RIVAL').some(r => r.tipo === 'Condición')).toBe(false)
  })
})
