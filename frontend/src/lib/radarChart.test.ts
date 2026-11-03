import { describe, expect, it } from 'vitest'
import { radarModel, radarSvg, RADAR_LABELS } from './radarChart'
import type { PlayerStat } from '@/api/client'
import vectors from '../../../tests/local_vectors/scouting_docx.json'

// The radar of the individual scouting (issue #717, 17c): the value of each metric of a player against the league is the one the server's `RadarChart` normalises, to the last digit
// (`tests/local_vectors/scouting_docx_vectors.py`); the drawing is the browser's and is checked for what it must show.
describe('the radar values say what the server\'s radar says', () => {
  it.each(vectors.leagues.map(l => [l.name, l] as const))('%s', (_name, league) => {
    const players = league.players as unknown as PlayerStat[]
    players.forEach((player, i) => {
      const model = radarModel(player, players)
      expect(model.values).toEqual(league.radar[i].values)
      expect(model.averages).toEqual(league.radar[i].averages)
    })
  })
})

describe('the drawing', () => {
  const players = vectors.leagues[0].players as unknown as PlayerStat[]
  it('has the sixteen metrics in four labelled groups, one bar per metric and the dashed league line', () => {
    const svg = radarSvg(radarModel(players[0], players), 'JUGADOR “Ñ” <&>')
    expect(RADAR_LABELS).toHaveLength(16)
    for (const label of [...RADAR_LABELS, 'Defensa', 'Tiro', 'Manejo', 'Estilo', 'Promedio Liga']) expect(svg).toContain(`>${label}<`)
    expect(svg).toContain('Análisis Radar - JUGADOR “Ñ” &lt;&amp;&gt;')            // the name is escaped, not injected
    expect((svg.match(/data-bar/g) ?? []).length).toBe(16)
    expect(svg).toContain('stroke-dasharray')
    expect(svg.startsWith('<svg')).toBe(true)
  })
  it('draws every player of both leagues without a NaN', () => {
    for (const league of vectors.leagues) {
      const all = league.players as unknown as PlayerStat[]
      for (const player of all) expect(radarSvg(radarModel(player, all), player.player_name ?? '')).not.toMatch(/NaN|undefined/)
    }
  })
})
