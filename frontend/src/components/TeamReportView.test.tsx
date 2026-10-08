import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import TeamReportView from './TeamReportView'
import type { TeamReport } from '@/api/teamReport'

const base: TeamReport = {
  team: 'Equipo A', mode: 'own', games_played: 20, low_sample: false,
  zones: [{ zone: 'paint', label: 'Pintura', points: 2, fga: 40, fg_pct: 60, league_pct: 45, delta_pp: 15, low_sample: false, kind: 'hot', text: 'Zona caliente.' }],
  strengths: [{ key: 'points_per_game', label: 'Puntos por partido', formatted: '90.0', quartile: 4, diff_pct: 15.4, kind: 'strength', text: 'Buena anotación.' }],
  weaknesses: [{ key: 'turnovers_per_game', label: 'Pérdidas por partido', formatted: '18.0', quartile: 4, diff_pct: 38, kind: 'weakness', text: 'Pierde demasiados balones.' }],
  differentials: [{ key: 'points_per_game', label: 'Puntos por partido', formatted: '90.0', diff_pct: 15.4, advantage: true }],
  consistency: [{ key: 'fg3_percentage', label: '% triples', cv: 40, status: 'inconsistent', n: 20, low_sample: false, text: 'Muy irregular.' }],
  profile: ['Ritmo alto: juega muchas posesiones.'],
  tactics: [{ key: 'points_per_game', label: 'Puntos por partido', area: 'ofensiva', kind: 'leverage', text: 'Potenciar.' }],
  training: [{ key: 'turnovers_per_game', label: 'Pérdidas por partido', area: 'ofensiva', kind: 'improve', text: 'Reducir pérdidas.', priority: 1 }],
}

describe('TeamReportView', () => {
  it('renders every section of an own-team report', () => {
    render(<TeamReportView report={base} />)
    for (const t of ['Puntos fuertes clave', 'Debilidades críticas', 'Perfil de equipo', 'Enfoque de entrenamiento'])
      expect(screen.getByText(t)).toBeTruthy()
    expect(screen.getByText('Buena anotación.')).toBeTruthy()
    expect(screen.getByText('Reducir pérdidas.')).toBeTruthy()
  })

  it('uses scouting wording in rival mode', () => {
    render(<TeamReportView report={{ ...base, mode: 'rival' }} />)
    expect(screen.getByText('Peligros a neutralizar')).toBeTruthy()
    expect(screen.getByText('Debilidades a explotar')).toBeTruthy()
  })

  it('shows an empty-state message for sections without findings', () => {
    render(<TeamReportView report={{ ...base, strengths: [], weaknesses: [], consistency: [] }} />)
    expect(screen.getAllByText('Sin datos destacados.').length).toBe(3)
  })

  it('shows the zone section with the gap vs league', () => {
    render(<TeamReportView report={base} />)
    expect(screen.getByText('Zonas de tiro')).toBeTruthy()
    expect(screen.getByText(/Pintura/)).toBeTruthy()
    expect(screen.getByText('Zona caliente.')).toBeTruthy()
    expect(screen.getByText(/\+15\.0 pp/)).toBeTruthy()
  })

  it('warns about a small sample (early season) instead of hiding the report', () => {
    render(<TeamReportView report={{ ...base, games_played: 2, low_sample: true }} />)
    expect(screen.getByText(/muestra pequeña/i)).toBeTruthy()
    expect(screen.getByText('Puntos fuertes clave')).toBeTruthy()
  })

  it('does not show the sample warning for a normal report', () => {
    render(<TeamReportView report={base} />)
    expect(screen.queryByText(/muestra pequeña/i)).toBeNull()
  })

  it('flags unreliable consistency values and zones', () => {
    render(<TeamReportView report={{
      ...base,
      consistency: [{ ...base.consistency[0], n: 2, low_sample: true }],
      zones: [{ ...base.zones[0], low_sample: true }],
    }} />)
    expect(screen.getAllByText(/poco fiable/i).length).toBe(2)
  })
})
