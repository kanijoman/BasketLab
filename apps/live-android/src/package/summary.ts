/** Human-readable description of a preparation package (what the user sees after importing). */
export interface PackageSummary {
  team: string
  rival: string
  season: string
  collection: string
  createdAt: string
  ownPlayers: number
  rivalPlayers: number
  games: { own: number; rival: number; league: number }
}

interface RawPackage {
  package?: {
    team?: { name?: string }
    rival?: { name?: string }
    season?: string
    collection?: string
    created_at?: string
    tables?: { players?: Record<string, unknown>; rival_players?: Record<string, unknown> }
    baselines?: { sample_games?: { own?: number; rival?: number; league?: number } }
  }
}

export function summarizePackage(text: string): PackageSummary {
  const body = (JSON.parse(text) as RawPackage).package
  if (!body) throw new Error('No es un paquete de preparación')
  const games = body.baselines?.sample_games ?? {}
  return {
    team: body.team?.name ?? '',
    rival: body.rival?.name ?? '',
    season: body.season ?? '',
    collection: body.collection ?? '',
    createdAt: body.created_at ?? '',
    ownPlayers: Object.keys(body.tables?.players ?? {}).length,
    rivalPlayers: Object.keys(body.tables?.rival_players ?? {}).length,
    games: { own: games.own ?? 0, rival: games.rival ?? 0, league: games.league ?? 0 },
  }
}
