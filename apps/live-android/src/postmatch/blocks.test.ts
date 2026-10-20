import { describe, expect, it } from 'vitest'
import { reportBlocks, safeText, type Block } from './blocks'
import type { PostMatchReport } from '../engine/types'

const FACTORS = { efg: 0.48, tov: 0.17, orb: 0.3, ftr: 0.24 }
const REPORT: PostMatchReport = {
  version: 1,
  match: {
    own: { id: '1', name: 'MIPELLETYMAS B.F. LEON' }, rival: { id: '2', name: 'RECOLETAS ZAMORA' }, home_id: '2',
    score: { own: 38, rival: 59 }, result: 'loss',
    periods: [
      { period: 1, label: 'Cuarto 1', own: 10, rival: 12, net: -2, keys: ['Pérdidas: 6 vs 3'], adjustments: ['Asegurar el balón en la salida de pista'],
        pace: { per40: 72, before40: null, own_habit40: 70, rival_habit40: 66 }, pace_text: 'Ritmo: 72 posesiones por 40 min (habitual: 70 el nuestro y 66 el rival).' },
      { period: 2, label: 'Cuarto 2', own: 6, rival: 14, net: -8, keys: [], adjustments: [], pace: null, pace_text: '' },
    ],
  },
  evolution: {
    lead_changes: 3, ties: 0, max_lead: { margin: 6, elapsed: 151 }, max_deficit: { margin: 25, elapsed: 2154 },
    timeline: [[0, 0], [60, 2], [120, 4], [180, -3], [2400, -21]], narrative: ['Máxima ventaja propia: 6 puntos (Q1 07:29).', '3 cambios de ventaja y 0 empates.'],
  },
  timeline: [[30, [2, 0]], [200, [2, 3]]],
  runs: [
    { team: 'rival', start: 1004, end: 1100, pts: 9, against: 2, period: 2, clock: 'Q2 06:44', score_before: [12, 14], score_after: [12, 23], lineup: ['A', 'B', 'C', 'D', 'E'],
      entered: ['C. CELAYA'], left: ['M. FERRERAS'], explanation: 'Claves: 3 pérdidas. Entraron C. CELAYA y salieron M. FERRERAS en los 2 minutos previos.' },
    { team: 'own', start: 300, end: 360, pts: 8, against: 0, period: 1, clock: 'Q1 05:00', score_before: [2, 2], score_after: [10, 2], lineup: ['A', 'B', 'C', 'D', 'E'],
      entered: [], left: [], explanation: 'Claves: 3 triples.' },
  ],
  lineups: {
    best: [{ players: ['A', 'B', 'C', 'D', 'E'], seconds: 240, pts_for: 10, pts_against: 6, net: 4 }],
    worst: [{ players: ['F', 'G', 'H', 'I', 'J'], seconds: 300, pts_for: 4, pts_against: 14, net: -10 }],
  },
  players: { top: [{ name: 'A. MARTIN', pm: 3, pts: 8, minutes: 1500 }], bottom: [{ name: 'F. DEMBELE', pm: -14, pts: 4, minutes: 1700 }] },
  four_factors: { own: FACTORS, rival: { efg: 0.55, tov: 0.12, orb: 0.28, ftr: 0.2 } },
  team: {
    own: { possessions: 62, rating: 61.3, factors: FACTORS, stats: {} }, rival: { possessions: 61, rating: 96.7, factors: FACTORS, stats: {} },
  },
  went_well: ['Rebote ofensivo (ORB %): 30 % frente a 28 % del rival.'],
  to_improve: ['Pérdidas (TOV %): 17 % frente a 12 % del rival.'],
  alerts: [
    { key: 'k1', id: 'fatigue_high', severity: 'warning', category: 'rotacion', message: 'F. DEMBELE: riesgo de fatiga alto', proposal: ['A → B'],
      period: 2, clock: '03:38', elapsed: 982, score: [6, 14] },
    { key: 'k2', id: 'x', severity: 'info', category: 'rival', message: 'Sin reloj', proposal: [], period: null, clock: null, elapsed: null, score: null },
  ],
}

const kinds = (blocks: Block[]) => blocks.map(b => b.kind)
const headings = (blocks: Block[]) => blocks.filter(b => b.kind === 'heading').map(b => (b as { text: string }).text)

describe('reportBlocks (issue #409)', () => {
  it('starts with the match and the result, then the sections in a reading order', () => {
    const blocks = reportBlocks(REPORT)
    expect(blocks[0]).toMatchObject({ kind: 'title', text: 'MIPELLETYMAS B.F. LEON – RECOLETAS ZAMORA' })
    expect((blocks[0] as { sub: string }).sub).toContain('Derrota 38-59')
    expect(headings(blocks)).toEqual([
      'Resumen por cuartos', 'Evolución del partido', 'Parciales y por qué se produjeron', 'Quintetos', 'Jugadoras (+/-)',
      'Four Factors', 'Lo que ha ido bien', 'Lo que podemos mejorar', 'Anexo: alertas del partido',
    ])
  })

  it('has the score of each quarter with its keys and adjustments', () => {
    const blocks = reportBlocks(REPORT)
    const table = blocks.find(b => b.kind === 'table') as Extract<Block, { kind: 'table' }>
    expect(table.rows).toEqual([['Cuarto 1', '10', '12', '-2'], ['Cuarto 2', '6', '14', '-8']])
    const text = JSON.stringify(blocks)
    expect(text).toContain('Pérdidas: 6 vs 3')
    expect(text).toContain('Ritmo: 72 posesiones por 40 min')                  // the pace of the quarter travels with its notes
    expect(text).toContain('Asegurar el balón en la salida de pista')
  })

  it('draws the evolution as a chart of the net score and says it in sentences', () => {
    const chart = reportBlocks(REPORT).find(b => b.kind === 'chart') as Extract<Block, { kind: 'chart' }>
    expect(chart.points).toEqual(REPORT.evolution.timeline)
    expect(JSON.stringify(reportBlocks(REPORT))).toContain('3 cambios de ventaja')
  })

  it('describes every run, in game order, with who was on court and the explanation', () => {
    const text = reportBlocks(REPORT).filter(b => b.kind === 'text').map(b => (b as { text: string }).text).join('\n')
    expect(text.indexOf('Q1 05:00')).toBeLessThan(text.indexOf('Q2 06:44'))
    expect(text).toContain('Parcial a favor 8-0')
    expect(text).toContain('Parcial en contra 2-9')
    expect(text).toContain('12-14 → 12-23')
    expect(text).toContain('En pista: A, B, C, D, E')
    expect(text).toContain('Entraron C. CELAYA')
  })

  it('lists the alerts with the clock and the score, and the ones without a readable clock last', () => {
    const table = reportBlocks(REPORT).filter(b => b.kind === 'table').pop() as Extract<Block, { kind: 'table' }>
    expect(table.head).toEqual(['Reloj', 'Marcador', 'Nivel', 'Tipo', 'Alerta'])
    expect(table.rows[0].slice(0, 3)).toEqual(['Q2 03:38', '6-14', 'Aviso'])
    expect(table.rows[0][4]).toContain('F. DEMBELE: riesgo de fatiga alto')
    expect(table.rows[0][4]).toContain('A → B')
    expect(table.rows[1].slice(0, 2)).toEqual(['—', '—'])
  })

  it('says so when there is nothing to list', () => {
    const blocks = reportBlocks({ ...REPORT, runs: [], alerts: [], went_well: [], to_improve: [] })
    const text = JSON.stringify(blocks)
    expect(text).toContain('Sin parciales de 8 o más puntos')
    expect(text).toContain('Sin alertas registradas')
    expect(kinds(blocks).filter(k => k === 'bullets').length).toBeGreaterThan(0)
  })

  it('keeps the text inside what the PDF font can print', () => {
    expect(safeText('≥ 8 → 5 · “x” – ñ á')).toBe('>= 8 -> 5 · "x" – ñ á')
    expect(safeText('Prórroga 1')).toBe('Prórroga 1')
  })

  it('prints the sigma of the substitution texts as words and any other character the font lacks as a question mark (issue #423)', () => {
    expect(safeText('cede algo en el acierto de tiro: -0.3 σ). Rol similar')).toBe('cede algo en el acierto de tiro: -0.3 desv.). Rol similar')
    expect(safeText('mejora el rebote defensivo (+0.8 σ)')).toBe('mejora el rebote defensivo (+0.8 desv.)')
    expect(safeText('Ω y ✓ y 😀')).toBe('? y ? y ?')
    expect(safeText('ÑñÁéÍóÚü ¿¡ ºª € — •')).toBe('ÑñÁéÍóÚü ¿¡ ºª € — •')
  })
})
