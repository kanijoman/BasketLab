// Análisis PBP on the device (issue #676): the five tables of the page summed from the `DERIVED` of each game (`derived/` of web-data), as the pipelines and services of
// `pbp_extended_stats_service`, `pbp_situation_stats_service` and `derived_coverage_service` sum them in Mongo. Parity: `pbp.test.ts` against `tests/local_vectors/pbp_*.json`.
// A game counts when its team entry says `reliable: true` (#390); one that is not is only counted (`games_unreliable`) and contributes nothing to a sum.
import type { DerivedCoverage, OriginRow, PeriodRow, SituationRow, TimeoutRow } from '@/api/pbpExtended'

const FT_POSSESSION_COST = 0.44
const ORIGIN_MIN_VERSION = 6               // every group needs the reliability flag of v5 (#390); the fast break (#398) is v6
const PERIOD_MIN_VERSION = 5
const SITUATION_MIN_VERSION = 5
const LISTED = 50                          // the games named in the coverage; the count is always the whole

type Entry = Record<string, any>           // eslint-disable-line @typescript-eslint/no-explicit-any -- a `DERIVED.TEAM` entry: the figures are read by name, as the pipelines do

/** What the exporter publishes of a competition (`export_derived`): the `DERIVED` of each game that has it, and the games that have none. */
export interface Derived {
  format: number
  collection: string
  league: 'feb' | 'fbcyl'
  games: number
  total: number
  without_derived: { code: string; teams: string[] }[]
  rows: { match_id: number | string; v: number | null; names: (string | null)[]; teams: Entry[] }[]
}

/** One team in one game: the entry, the rival's, the name and whether the game counts. */
interface Side { game: number | string; me: Entry; rival: Entry | undefined; name: string | null; used: boolean; doubtful: boolean }

/** The stable id of a team in a game (FBCYL groups a season by `ext_id`), as it is stored; a map is keyed by its text. */
const teamId = (entry: Entry): unknown => entry.ext_id ?? entry.id
const teamKey = (entry: Entry): string => String(teamId(entry))
const num = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) ? value : 0)       // `$sum` adds what is a number
const ratio = (numerator: number, denominator: number, scale = 1): number | null => (denominator ? (numerator / denominator) * scale : null)

/** The two sides of every game of at least `minVersion` (`$match` + `$unwind` of the pipelines). */
function sides(derived: Derived, minVersion: number): Side[] {
  return derived.rows.filter(row => row.v !== null && row.v >= minVersion).flatMap(row =>
    row.teams.map((me, i) => {
      const used = me.reliable === true
      return { game: row.match_id, me, rival: row.teams[1 - i], name: row.names[i] ?? null, used, doubtful: used && me.quality_level !== 'ok' }
    }))
}

function groupBy<T>(items: T[], key: (item: T) => string): Map<string, T[]> {
  const groups = new Map<string, T[]>()
  for (const item of items) groups.set(key(item), [...(groups.get(key(item)) ?? []), item])
  return groups
}

const byName = (a: Record<string, unknown>, b: Record<string, unknown>) => (String(a.team_name) < String(b.team_name) ? -1 : String(a.team_name) > String(b.team_name) ? 1 : 0)

// ── Points by origin ────────────────────────────────────────────────────────────────────────────────────────────────────

const SUMMED = ['pts_off_tov', 'poss_off_tov', 'pts_off_steal', 'poss_off_steal', 'pts_second_chance', 'poss_second_chance', 'pts_bench', 'pts_paint', 'pts_fastbreak',
  'poss_transition', 'pts', 'possessions'] as const
const POINTS = ['pts_off_tov', 'pts_off_steal', 'pts_second_chance', 'pts_bench', 'pts_paint', 'pts_fastbreak'] as const
const ORIGINS: Record<string, string> = { off_tov: 'poss_off_tov', off_steal: 'poss_off_steal', second_chance: 'poss_second_chance', fastbreak: 'poss_transition' }

export function pointsByOrigin(derived: Derived): OriginRow[] {
  const rows = [...groupBy(sides(derived, ORIGIN_MIN_VERSION), side => teamKey(side.me)).values()].map(group => {
    const raw: Record<string, number> = { games: 0, games_unreliable: 0, games_doubtful: 0, games_paint: 0 }
    for (const field of SUMMED) { raw[field] = 0; raw[`opp_${field}`] = 0 }
    for (const side of group) {
      if (side.used) {
        raw.games += 1
        if (typeof side.me.pts_paint === 'number') raw.games_paint += 1
        for (const field of SUMMED) { raw[field] += num(side.me[field]); raw[`opp_${field}`] += num(side.rival?.[field]) }
      } else raw.games_unreliable += 1
      if (side.doubtful) raw.games_doubtful += 1
    }
    return teamRow(teamId(group[0].me), group[0].name, raw)
  })
  return rows.sort(byName) as unknown as OriginRow[]
}

function teamRow(id: unknown, name: string | null, raw: Record<string, number>): Record<string, unknown> {
  const games = raw.games
  const row: Record<string, unknown> = { team_id: id, team_name: name, games, games_unreliable: raw.games_unreliable, games_doubtful: raw.games_doubtful, games_paint: raw.games_paint }
  for (const prefix of ['', 'opp_']) {
    for (const field of POINTS) {
      const key = prefix + field
      const hasData = games && (field !== 'pts_paint' || raw.games_paint)
      row[key] = hasData ? raw[key] : null
      row[`${key}_per_game`] = hasData ? ratio(raw[key], games) : null
    }
    for (const [origin, possessions] of Object.entries(ORIGINS)) row[`${prefix}oer_${origin}`] = ratio(raw[`${prefix}pts_${origin}`], raw[prefix + possessions], 100)
    row[`${prefix}bench_pct`] = ratio(raw[`${prefix}pts_bench`], raw[`${prefix}pts`], 100)
    // «after a turnover» without the steals (#602)
    const points = raw[`${prefix}pts_off_tov`] - raw[`${prefix}pts_off_steal`]
    const possessions = raw[`${prefix}poss_off_tov`] - raw[`${prefix}poss_off_steal`]
    row[`${prefix}pts_off_loss`] = games ? points : null
    row[`${prefix}pts_off_loss_per_game`] = games ? ratio(points, games) : null
    row[`${prefix}oer_off_loss`] = ratio(points, possessions, 100)
    // per 100 possessions of the team (#603)
    row[`${prefix}possessions`] = games ? raw[`${prefix}possessions`] : null
    for (const field of ['pts_off_loss', 'pts_off_steal', 'pts_second_chance', 'pts_bench', 'pts_paint', 'pts_fastbreak']) {
      const value = row[prefix + field] as number | null
      row[`${prefix}${field}_per_100`] = value !== null ? ratio(value, raw[`${prefix}possessions`], 100) : null
    }
  }
  return row
}

// ── By period ───────────────────────────────────────────────────────────────────────────────────────────────────────────

const COUNTERS = ['pts', 'poss', 'fga', 'fgm', 'fg3m', 'fta', 'ftm', 'tov', 'orb', 'drb', 'fouls'] as const

function periodRow(raw: Record<string, number>, games: number): Record<string, unknown> {
  const { fga, fta } = raw
  const oppFga = raw.opp_fga, oppFta = raw.opp_fta
  const efg = (p: string, att: number) => ratio(raw[`${p}fgm`] + 0.5 * raw[`${p}fg3m`], att, 100)
  const tov = (p: string, att: number, ft: number) => ratio(raw[`${p}tov`], att + FT_POSSESSION_COST * ft + raw[`${p}tov`], 100)
  return {
    games, minutes: raw.minutes, pts: raw.pts, opp_pts: raw.opp_pts, pts_per_game: raw.pts / games, opp_pts_per_game: raw.opp_pts / games, poss: raw.poss, opp_poss: raw.opp_poss,
    ortg: ratio(raw.pts, raw.poss, 100), drtg: ratio(raw.opp_pts, raw.opp_poss, 100),
    net_rating: raw.poss && raw.opp_poss ? (raw.pts / raw.poss - raw.opp_pts / raw.opp_poss) * 100 : null,
    pace: ratio(raw.poss * 40, raw.minutes),
    efg_pct: efg('', fga), opp_efg_pct: efg('opp_', oppFga), tov_pct: tov('', fga, fta), opp_tov_pct: tov('opp_', oppFga, oppFta),
    orb_pct: ratio(raw.orb, raw.orb + raw.opp_drb, 100), drb_pct: ratio(raw.drb, raw.drb + raw.opp_orb, 100),
    ftr: ratio(fta, fga, 100), opp_ftr: ratio(oppFta, oppFga, 100),
    fouls_per_game: raw.fouls / games, opp_fouls_per_game: raw.opp_fouls / games,
  }
}

export function byPeriod(derived: Derived): PeriodRow[] {
  const teams = new Map<string, Record<string, unknown> & { periods: Record<string, unknown> }>()
  for (const [key, group] of groupBy(sides(derived, PERIOD_MIN_VERSION), side => teamKey(side.me))) {
    const buckets = new Map<string, { sides: Side[]; periods: Entry[] }>()
    for (const side of group) {
      for (const period of (side.me.periods ?? []) as Entry[]) {
        const bucket = period.p <= 4 ? String(period.p) : 'OT'
        const entry = buckets.get(bucket) ?? { sides: [], periods: [] }
        entry.sides.push(side); entry.periods.push(period)
        buckets.set(bucket, entry)
      }
    }
    if (buckets.size === 0) continue                              // a team with no period at all has no row
    const team = { team_id: teamId(group[0].me), team_name: group[0].name, games: 0, games_unreliable: 0, games_doubtful: 0, periods: {} as Record<string, unknown> }
    teams.set(key, team)
    for (const [bucket, { sides: inBucket, periods }] of buckets) {
      const used = periods.map((p, i) => ({ p, side: inBucket[i] })).filter(entry => entry.side.used)
      const games = new Set(used.map(entry => entry.side.game)).size
      if (bucket === '1') {
        team.games = games
        team.games_unreliable = new Set(inBucket.filter(s => !s.used).map(s => s.game)).size
        team.games_doubtful = new Set(inBucket.filter(s => s.doubtful).map(s => s.game)).size
      }
      if (games) {
        const raw: Record<string, number> = { minutes: used.reduce((n, e) => n + num(e.p.minutes), 0) }
        for (const field of COUNTERS) {
          raw[field] = used.reduce((n, e) => n + num(e.p[field]), 0)
          raw[`opp_${field}`] = used.reduce((n, e) => n + num(e.p[`opp_${field}`]), 0)
        }
        team.periods[bucket] = periodRow(raw, games)
      }
    }
  }
  for (const team of teams.values()) {
    team.periods = Object.fromEntries(Object.entries(team.periods).sort(([a], [b]) => (a === 'OT' ? 99 : Number(a)) - (b === 'OT' ? 99 : Number(b))))
  }
  return [...teams.values()].sort(byName) as unknown as PeriodRow[]
}

// ── Situations and timeouts ─────────────────────────────────────────────────────────────────────────────────────────────

const EDGE_KEYS = ['pts', 'opp_pts', 'poss', 'opp_poss', 'tov', 'opp_tov'] as const
type Edge = Record<(typeof EDGE_KEYS)[number], number>

const net = (pts: number, oppPts: number, poss: number, oppPoss: number): number | null => (poss && oppPoss ? (pts / poss - oppPts / oppPoss) * 100 : null)

function edge(values: Edge, games: number): Record<string, unknown> {
  return {
    ...values, pts_per_game: games ? values.pts / games : null, net_rating: net(values.pts, values.opp_pts, values.poss, values.opp_poss),
    tov_pct: ratio(values.tov, values.poss, 100), opp_tov_pct: ratio(values.opp_tov, values.opp_poss, 100),
  }
}

export function situations(derived: Derived): SituationRow[] {
  const rows = [...groupBy(sides(derived, SITUATION_MIN_VERSION), side => teamKey(side.me)).values()].map(group => {
    const raw = { games: 0, unreliable: 0, doubtful: 0 }
    const block: Record<string, { n: number; pts: number }> = { ato_own: { n: 0, pts: 0 }, ato_rival: { n: 0, pts: 0 }, first_poss: { n: 0, pts: 0 } }
    const zero = (): Edge => ({ pts: 0, opp_pts: 0, poss: 0, opp_poss: 0, tov: 0, opp_tov: 0 })
    const start = zero(), end = zero(), total = zero()
    for (const side of group) {
      for (const key of EDGE_KEYS) total[key] += ((side.me.periods ?? []) as Entry[]).reduce((n, p) => n + (side.used ? num(p[key]) : 0), 0)
      if (side.doubtful) raw.doubtful += 1
      if (!side.used) { raw.unreliable += 1; continue }
      raw.games += 1
      for (const name of Object.keys(block)) { block[name].n += num(side.me[name]?.n); block[name].pts += num(side.me[name]?.pts) }
      for (const key of EDGE_KEYS) { start[key] += num(side.me.edges?.start?.[key]); end[key] += num(side.me.edges?.end?.[key]) }
    }
    const edges: Record<string, Record<string, unknown>> = { start: edge(start, raw.games), end: edge(end, raw.games) }
    const rest = Object.fromEntries(EDGE_KEYS.map(key => [key, total[key] - start[key] - end[key]])) as Edge
    edges.rest = edge(rest, raw.games)
    for (const window of ['start', 'end']) {
      const a = edges[window].net_rating as number | null, b = edges.rest.net_rating as number | null
      edges[window].vs_rest = a !== null && b !== null ? a - b : null
    }
    const blockRow = (name: string) => ({ n: block[name].n, pts: block[name].pts, ppp: ratio(block[name].pts, block[name].n) })
    return { team_id: teamId(group[0].me), team_name: group[0].name, games: raw.games, games_unreliable: raw.unreliable, games_doubtful: raw.doubtful,
             ato_own: blockRow('ato_own'), ato_rival: blockRow('ato_rival'), first_poss: blockRow('first_poss'), edges }
  })
  return rows.sort(byName) as unknown as SituationRow[]
}

const timeoutNet = (side: Entry | undefined): number => {
  const part = (num_: string, den: string) => (num(side?.[den]) > 0 ? num(side?.[num_]) / num(side?.[den]) : 0)
  return (part('pts', 'poss') - part('opp_pts', 'opp_poss')) * 100
}

export function timeoutEffects(derived: Derived): TimeoutRow[] {
  const teams = new Map<string, { team_id: unknown; team_name: string | null; groups: Record<string, { n: number; before: number[]; after: number[]; improved: number; worsened: number }>; doubtful: Set<number | string> }>()
  for (const side of sides(derived, SITUATION_MIN_VERSION).filter(s => s.used)) {
    const key = teamKey(side.me)
    const team = teams.get(key) ?? { team_id: teamId(side.me), team_name: side.name, groups: {}, doubtful: new Set() }
    teams.set(key, team)
    if (side.doubtful) team.doubtful.add(side.game)
    for (const timeout of (side.me.timeouts ?? []) as Entry[]) {
      if (timeout?.caller !== 'own' && timeout?.caller !== 'rival') continue
      const before = timeoutNet(timeout.pre), after = timeoutNet(timeout.post)
      const group = team.groups[timeout.caller] ?? { n: 0, before: [], after: [], improved: 0, worsened: 0 }
      group.n += 1; group.before.push(before); group.after.push(after)
      if (after - before > 0) group.improved += 1
      if (after - before < 0) group.worsened += 1
      team.groups[timeout.caller] = group
    }
  }
  const mean = (values: number[]) => values.reduce((a, b) => a + b, 0) / values.length
  const timeoutGroup = (group: { n: number; before: number[]; after: number[]; improved: number; worsened: number } | undefined, caller: 'own' | 'rival') => {
    if (!group || !group.n) return { n: 0, net_rating_before: null, net_rating_after: null, delta_net_rating: null, pct_caller_improves: null }
    const before = mean(group.before), after = mean(group.after)
    const helped = caller === 'own' ? group.improved : group.worsened            // after the rival's timeout, our fall is the caller's gain
    return { n: group.n, net_rating_before: before, net_rating_after: after, delta_net_rating: after - before, pct_caller_improves: (helped / group.n) * 100 }
  }
  return [...teams.values()].map(t => ({ team_id: t.team_id, team_name: t.team_name, games_doubtful: t.doubtful.size, own: timeoutGroup(t.groups.own, 'own'), rival: timeoutGroup(t.groups.rival, 'rival') }))
    .sort(byName) as unknown as TimeoutRow[]
}

// ── Coverage ────────────────────────────────────────────────────────────────────────────────────────────────────────────

/** How many games lack the `DERIVED` the tables need (none, or of a version older than the origin tables ask for) and which (the first 50, in `_id` order). */
export function derivedCoverage(derived: Derived): DerivedCoverage & { collection: string; min_version: number } {
  const old = derived.rows.filter(row => row.v === null || row.v < ORIGIN_MIN_VERSION).map(row => ({ code: String(row.match_id), teams: row.names.filter((n): n is string => Boolean(n)) }))
  const pending = [...derived.without_derived, ...old]
  const order = derived.league === 'feb' ? (a: string, b: string) => Number(a) - Number(b) : (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0)       // as Mongo sorts `_id`
  pending.sort((a, b) => order(a.code, b.code))
  return { collection: derived.collection, min_version: ORIGIN_MIN_VERSION, total: derived.total, pending: pending.length, pending_games: pending.slice(0, LISTED) }
}
