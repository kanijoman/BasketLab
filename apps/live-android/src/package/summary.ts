/** Human-readable description of a preparation package (what the user sees after importing). */
export interface PackageSummary {
  team: string
  /** FEB id of the team the package is for (with the match code it says WHICH package is loaded, issue #342). */
  teamId: string
  rival: string
  rivalId: string
  season: string
  collection: string
  createdAt: string
  ownPlayers: number
  rivalPlayers: number
  games: { own: number; rival: number; league: number }
  /** The FEB match the package was prepared for (details only when the calendar was available). */
  match: PackageMatch | null
  /** The package's rule config (its gender goes to the text of the PDF report, #475). */
  ruleConfig?: Record<string, unknown>
}

export interface PackageMatch {
  code: string
  start?: string
  round?: number
  home?: { id: string; name: string }
  away?: { id: string; name: string }
}

interface RawPackage {
  package?: {
    team?: { id?: string; name?: string }
    rival?: { id?: string; name?: string }
    season?: string
    collection?: string
    created_at?: string
    tables?: { players?: Record<string, unknown>; rival_players?: Record<string, unknown> }
    baselines?: { sample_games?: { own?: number; rival?: number; league?: number } }
    competition_meta?: { match?: PackageMatch }
    rule_config?: Record<string, unknown>
  }
}

export function summarizePackage(text: string): PackageSummary {
  const body = (JSON.parse(text) as RawPackage).package
  if (!body) throw new Error('No es un paquete de preparación')
  const games = body.baselines?.sample_games ?? {}
  return {
    team: body.team?.name ?? '',
    teamId: String(body.team?.id ?? ''),
    rival: body.rival?.name ?? '',
    rivalId: String(body.rival?.id ?? ''),
    season: body.season ?? '',
    collection: body.collection ?? '',
    createdAt: body.created_at ?? '',
    ownPlayers: Object.keys(body.tables?.players ?? {}).length,
    rivalPlayers: Object.keys(body.tables?.rival_players ?? {}).length,
    games: { own: games.own ?? 0, rival: games.rival ?? 0, league: games.league ?? 0 },
    match: body.competition_meta?.match ?? null,
    ruleConfig: body.rule_config ?? {},
  }
}
