import { unzipSync, strFromU8 } from 'fflate'
import { describe, expect, it } from 'vitest'
import vectors from '../../../tests/local_vectors/weekly_rows.json'
import { weeklyReportFiles, weeklyReportZip, type WeeklyData } from './weeklyReport'
import type { Row } from './weeklyRows'

// The weekly report in the browser (issue #716, D4b): the same files in the same folders as the ZIP the server made, from the tables and the charts the page already reads. The images are
// drawn by the browser; here the drawing is replaced by its own SVG as bytes, so what each file says can be read.
const sample = vectors.leagues[0]
const TEAMS = sample.teams as Row[]
const [A, B] = [String(TEAMS[0].team_name), String(TEAMS[1].team_name)]
const text = (bytes: Uint8Array) => strFromU8(bytes)
const shots = (n: number) => Array.from({ length: n }, (_, i) => ({ x: 7.5, y: 2 + i, made: i % 2 === 0, zone: 'restricted_area' }))

function data(over: Partial<WeeklyData> = {}): WeeklyData & { filters: unknown[] } {
  const filters: unknown[] = []
  return {
    filters,
    teamStats: async filter => { filters.push(filter); return { team_stats: TEAMS, opponent_stats: TEAMS.map(t => ({ ...t, points_per_game: 60 })) } },
    consistency: async () => (sample.consistency as never),
    lastMatch: async name => ({ team: TEAMS[0], opponent: TEAMS[1], opponentName: name === A ? B : A, date: '03-11-2025' }),
    players: async () => (sample.players as Row[]).map((p, i) => ({ ...p, player_id: `p${i}`, team_name: i < 3 ? A : B })),
    shots: async (_team, player) => shots(player === 'p0' ? 9 : player ? 2 : 14),
    zones: async () => [],
    ...over,
  }
}
const render = async (svg: string) => new TextEncoder().encode(svg)
const input = { teamA: { id: '1', name: A }, teamB: { id: '2', name: B }, today: new Date(Date.UTC(2025, 10, 15, 12)) }
const names = async (over?: Partial<WeeklyData>) => Object.keys(await weeklyReportFiles(input, data(over), render)).sort()

describe('the files of the report', () => {
  it('has the folders and the names the server made: the general tables, the last game of each team and, per team, its players and its shot charts', async () => {
    const files = await names()
    for (const prefix of ['01', '02', '03', '04']) for (const kind of ['Basicas', 'Avanzadas']) {
      expect(files.filter(f => f.startsWith(`General/${prefix}_${kind}_`)), `${prefix} ${kind}`).toHaveLength(2)            // the competition and its rivals
    }
    expect(files).toEqual(expect.arrayContaining([
      'General/01_Basicas_Toda_Competicion.png', 'General/01_Avanzadas_Toda_Competicion_Rival.png', 'General/02_Basicas_Ganados_vs_Perdidos.png', 'General/03_Avanzadas_Local_vs_Visitante_Rival.png',
      'General/04_Basicas_Último_Mes.png', 'General/06_Consistencia_Liga.png', `General/05_Ultimo_Partido_${A}.png`, `General/05_Ultimo_Partido_${B}.png`,
      `${A}/1_Estadisticas_Individuales/01_${A}_Promedios.png`, `${A}/1_Estadisticas_Individuales/02_${A}_Totales.png`, `${A}/1_Estadisticas_Individuales/03_${A}_Proyeccion_30min.png`,
      `${A}/2_Graficos_Lanzamiento/Equipo/${A}_Mapa_Calor.png`, `${A}/2_Graficos_Lanzamiento/Equipo/${A}_Zonas.png`,
      `${B}/1_Estadisticas_Individuales/01_${B}_Promedios.png`, `${B}/2_Graficos_Lanzamiento/Equipo/${B}_Zonas.png`,
    ]))
    expect(files.filter(f => f.startsWith('General/'))).toHaveLength(8 + 8 + 2 + 1)                                              // 4 pairs x (basic + advanced) x 2, the two last games, the consistency
  })

  it('draws a player\'s charts only with five shots or more, and names the folder after the player', async () => {
    const files = await names()
    const players = files.filter(f => f.includes('/Jugadoras/'))
    expect(players.every(f => f.includes('/Jugadoras/'))).toBe(true)
    expect(players.some(f => f.includes(`${(sample.players as Row[])[0].player_name}`))).toBe(true)         // p0 has 9 shots
    expect(players.filter(f => f.startsWith(`${A}/`))).toHaveLength(2)                                    // p1 and p2 have 2: none
    expect(players.every(f => f.endsWith('_Mapa_Calor.png') || f.endsWith('_Zonas.png'))).toBe(true)
  })

  it('writes in a file name nothing the file system refuses', async () => {
    const files = await names({ players: async () => [{ ...(sample.players as Row[])[0], player_id: 'p0', player_name: 'Ana: "La/Fuerte"?', team_name: A }] })
    expect(files.filter(f => f.includes('Jugadoras'))[0]).toBe(`${A}/2_Graficos_Lanzamiento/Jugadoras/Ana_ _La_Fuerte__/Ana_ _La_Fuerte___Mapa_Calor.png`)
  })
})

describe('what the tables say', () => {
  it('has the rival tables rated the other way round, with the title of the rival', async () => {
    const files = await weeklyReportFiles(input, data(), render)
    const own = text(files['General/01_Basicas_Toda_Competicion.png']), rival = text(files['General/01_Basicas_Toda_Competicion_Rival.png'])
    expect(own).toContain('Estadísticas Básicas - Toda la Competición<')
    expect(rival).toContain('Estadísticas Básicas - Toda la Competición (Rival)<')
    expect(own).not.toEqual(rival)
  })

  it('asks the month as the last thirty days against everything before, and the rest as win/loss and home/away', async () => {
    const fake = data()
    await weeklyReportFiles(input, fake, render)
    expect(fake.filters).toEqual(expect.arrayContaining([{}, { result: 'won' }, { result: 'lost' }, { venue: 'home' }, { venue: 'away' }, { from: '2025-10-16' }, { to: '2025-10-15' }]))
  })

  it('puts the difference with the rest of the season in the comparisons and says so when no team has both halves', async () => {
    const files = await weeklyReportFiles(input, data(), render)
    expect(text(files['General/02_Basicas_Ganados_vs_Perdidos.png'])).toMatch(/\(\+?-?\d+\.\d\)/)
    const none = await weeklyReportFiles(input, data({ teamStats: async filter => ({ team_stats: 'result' in filter && filter.result === 'lost' ? [] : TEAMS, opponent_stats: [] }) }), render)
    expect(text(none['General/02_Basicas_Ganados_vs_Perdidos.png'])).toContain('(datos insuficientes)')
    expect(text(none['General/02_Basicas_Ganados_vs_Perdidos.png'])).toContain('Sin datos')
  })

  it('titles the last game with the team and the day, and leaves it out with no game or no season row of one of the two teams', async () => {
    const files = await weeklyReportFiles(input, data(), render)
    expect(text(files[`General/05_Ultimo_Partido_${A}.png`])).toContain(`Último Partido - ${A} - 03-11-2025`)
    const without = await names({ lastMatch: async () => null })
    expect(without.some(f => f.includes('05_Ultimo_Partido'))).toBe(false)
    const unknownRival = await names({ lastMatch: async () => ({ team: TEAMS[0], opponent: TEAMS[1], opponentName: 'Otro', date: '01-01-2025' }) })
    expect(unknownRival.some(f => f.includes('05_Ultimo_Partido'))).toBe(false)
  })

  it('titles the player tables of a team and has one row per player of that team only', async () => {
    const files = await weeklyReportFiles(input, data(), render)
    const avg = text(files[`${A}/1_Estadisticas_Individuales/01_${A}_Promedios.png`])
    expect(avg).toContain(`${A} - Promedios<`)
    expect((avg.match(/data-tone="plain"/g) ?? []).length).toBeGreaterThan(0)
    expect(text(files[`${A}/1_Estadisticas_Individuales/03_${A}_Proyeccion_30min.png`])).toContain(`${A} - Proyeccion 30min<`)
  })
})

describe('what is missing is left out, as the server did', () => {
  it('has no consistency table without data or when it cannot be read, and no player tables for a team with no players', async () => {
    expect((await names({ consistency: async () => ({}) })).some(f => f.includes('06_Consistencia'))).toBe(false)
    expect((await names({ consistency: async () => { throw new Error('no') } })).some(f => f.includes('06_Consistencia'))).toBe(false)
    expect((await names({ players: async () => [] })).some(f => f.includes('1_Estadisticas_Individuales'))).toBe(false)
  })

  it('has no shot charts for a team with no shots, and a chart that fails to draw is skipped without losing the rest', async () => {
    expect((await names({ shots: async () => [] })).some(f => f.includes('2_Graficos_Lanzamiento'))).toBe(false)
    let calls = 0
    const flaky = async (svg: string) => { if (++calls === 1) throw new Error('canvas'); return render(svg) }
    const files = await weeklyReportFiles(input, data(), flaky)
    expect(Object.keys(files).length).toBeGreaterThan(20)
  })

  it('has no tables at all for a competition with no teams, only the placeholders of the comparisons', async () => {
    const empty = await names({ teamStats: async () => ({ team_stats: [], opponent_stats: [] }), players: async () => [], shots: async () => [], lastMatch: async () => null, consistency: async () => ({}) })
    expect(empty.every(f => /^General\/0[234]_/.test(f))).toBe(true)
  })
})

describe('the progress and the zip', () => {
  it('reports five steps with the same words as the server', async () => {
    const steps: Array<[number, number, string]> = []
    await weeklyReportFiles(input, data(), render, (step, total, message) => steps.push([step, total, message]))
    expect(steps.map(s => s[0])).toEqual([1, 2, 3, 4, 5])
    expect(steps.every(s => s[1] === 5)).toBe(true)
    expect(steps.map(s => s[2])).toEqual(['Estadísticas generales de competición', `Último partido — ${A}`, `Último partido — ${B}`, `Informe equipo — ${A}`, `Informe equipo — ${B}`])
  })

  it('is a zip whose entries are the files, with the folders as paths', async () => {
    const blob = await weeklyReportZip(input, data(), render)
    expect(blob.type).toBe('application/zip')
    const entries = unzipSync(new Uint8Array(await blob.arrayBuffer()))
    expect(Object.keys(entries)).toContain('General/01_Basicas_Toda_Competicion.png')
    expect(text(entries['General/01_Basicas_Toda_Competicion.png'])).toContain('<svg')
  })
})
