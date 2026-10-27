/**
 * Columns, flattened rows and colour rules of the four tables of «Análisis pbp» (#359): points by origin, by period,
 * situations (after timeouts, first possessions, first / last two minutes) and the effect of the timeouts.
 */
import type { ColumnDef } from '@tanstack/react-table'

import type { PeriodRow, SituationRow, TimeoutRow } from '@/api/pbpExtended'
import TeamCell from '@/components/ui/TeamCell'
import Tooltip from '@/components/ui/Tooltip'
import { fmt } from '@/lib/utils'

type Col = ColumnDef<any, unknown> // eslint-disable-line @typescript-eslint/no-explicit-any

export const TEAM_COLUMN_SIZE = 240
export const NUMERIC_COLUMN_SIZE = 66

// -- Cells --------------------------------------------------------------------

const teamCol: Col = {
  id: 'team_name',
  accessorKey: 'team_name',
  header: 'Equipo',
  size: TEAM_COLUMN_SIZE,
  cell: ({ getValue, row }) => <TeamCell name={getValue() as string} teamId={row.original.team_id} />,
}

function head(short: string, description: string): () => JSX.Element {
  return () => (
    <Tooltip text={description}>
      <span className="underline decoration-dotted underline-offset-2">{short}</span>
    </Tooltip>
  )
}

/** Numeric column; a missing value (no sample, no data) shows an em dash, never a 0. */
function num(key: string, short: string, description: string, decimals = 1, suffix = ''): Col {
  return {
    id: key,
    accessorKey: key,
    header: head(short, description),
    cell: ({ getValue }) => {
      const v = getValue() as number | null | undefined
      return v == null ? <span className="text-ink-disabled">—</span> : `${fmt(v, decimals)}${suffix}`
    },
  }
}

const games = num('games', 'PJ', 'Partidos con datos fiables', 0)
const excluded = num('games_unreliable', 'Excl.', 'Partidos excluidos por poco fiables: más del 10 % de sus puntos en posesiones de origen desconocido, o un recuento de posesiones que difiere más del 10 % de la estimación', 0)

// -- Points by origin ---------------------------------------------------------

export type OriginView = 'own' | 'opp'

export const ORIGIN_VIEWS: { key: OriginView; label: string }[] = [
  { key: 'own', label: 'Propios' },
  { key: 'opp', label: 'Concedidos (rival)' },
]

/**
 * Every origin is said by possessions (#603). A turnover, a steal and a second chance are KINDS OF POSSESSION: their OER is the points per 100 possessions that started
 * that way (the count per game stays next to it). The bench, the paint and the fast break are points, not a kind of possession: they go per 100 possessions of the team.
 * «Tras pérdida» leaves the steals out, which have their own group (#602). The fast break has no OER: its denominator was every possession that starts in transition, so
 * it was the share of them that ends in a quick basket, not an efficiency.
 */
export function originColumns(view: OriginView): Col[] {
  const p = view === 'opp' ? 'opp_' : ''
  const who = view === 'opp' ? ' que concede el equipo' : ''
  const team = view === 'opp' ? 'del rival' : 'del equipo'
  const group = (id: string, header: string, columns: Col[]): Col => ({ id: `${p}grp_${id}`, header, columns })
  const perGame = (origin: string, what: string): Col => num(`${p}pts_${origin}_per_game`, 'Pts/P', `Puntos por partido ${what}${who}`)
  const per100 = (origin: string, what: string): Col => num(`${p}pts_${origin}_per_100`, 'Pts/100', `Puntos ${what} por 100 posesiones ${team}${who}`)
  return [
    teamCol, games, excluded,
    group('tov', 'Tras pérdida', [
      perGame('off_loss', 'en posesiones tras pérdida que no es robo (el robo tiene su columna)'),
      num(`${p}oer_off_loss`, 'OER', `Puntos por 100 posesiones que empiezan tras una pérdida que no es robo${who}`),
    ]),
    group('steal', 'Tras robo', [
      perGame('off_steal', 'en posesiones tras robo'),
      num(`${p}oer_off_steal`, 'OER', `Puntos por 100 posesiones que empiezan tras robo${who}`),
    ]),
    group('fastbreak', 'Contraataque (est.)', [
      per100('fastbreak', 'de canastas en ≤ 6 s tras pérdida rival (con o sin robo) o rebote defensivo (estimación propia, no la de la FEB)'),
    ]),
    group('second', '2ª oportunidad', [
      perGame('second_chance', 'tras rebote ofensivo de la misma posesión'),
      num(`${p}oer_second_chance`, 'OER', `Puntos por 100 posesiones con rebote ofensivo${who}`),
    ]),
    group('bench', 'Banquillo', [
      per100('bench', 'de jugadoras no titulares'),
      num(`${p}bench_pct`, '%', `Porcentaje de los puntos que anota el banquillo${who}`),
    ]),
    group('paint', 'Pintura', [
      per100('paint', 'de canastas en el aro y la zona'),
    ]),
  ]
}

const ORIGIN_NUMERIC = [
  'pts_off_loss_per_game', 'oer_off_loss', 'pts_off_steal_per_game', 'oer_off_steal', 'pts_fastbreak_per_100',
  'pts_second_chance_per_game', 'oer_second_chance', 'pts_bench_per_100', 'bench_pct', 'pts_paint_per_100',
]

/** The numeric columns of the table (the ones the quartile colours are computed for) in a view. */
export const ORIGIN_KEYS = (view: OriginView): string[] => ORIGIN_NUMERIC.map(k => (view === 'opp' ? `opp_${k}` : k))

/** Lower is better only for what the rival scores against the team; the bench share conceded is not good or bad. */
export const ORIGIN_REVERSE: Record<OriginView, string[]> = {
  own: [],
  opp: ORIGIN_KEYS('opp').filter(k => k !== 'opp_bench_pct'),
}

// -- By period ----------------------------------------------------------------

export const PERIODS = [
  { key: '1', label: 'Q1' }, { key: '2', label: 'Q2' }, { key: '3', label: 'Q3' }, { key: '4', label: 'Q4' }, { key: 'OT', label: 'Prórroga' },
]

export type PeriodTableRow = Record<string, number | string | null | undefined> & { team_id: string; team_name: string }

/** One row per team with the figures of one period; teams that never played it (overtime) are left out. */
export function flattenPeriod(rows: PeriodRow[], period: string): PeriodTableRow[] {
  return rows.flatMap(r => {
    const figures = r.periods[period]
    return figures ? [{ team_id: r.team_id, team_name: r.team_name, ...figures, games_unreliable: r.games_unreliable }] : []
  })
}

export function periodColumns(): Col[] {
  return [
    teamCol, games, excluded,
    num('pts_per_game', 'Pts', 'Puntos a favor por partido en el periodo'),
    num('opp_pts_per_game', 'Pts contra', 'Puntos en contra por partido en el periodo'),
    num('ortg', 'ORtg', 'Puntos por 100 posesiones del equipo'),
    num('drtg', 'DRtg', 'Puntos por 100 posesiones del rival'),
    num('net_rating', 'Net', 'ORtg − DRtg'),
    num('pace', 'Ritmo', 'Posesiones por 40 minutos'),
    num('efg_pct', 'eFG%', 'Porcentaje efectivo de tiro de campo'),
    num('tov_pct', 'TOV%', 'Pérdidas por posesión (con los tiros libres a 0,44)'),
    num('orb_pct', 'ORB%', 'Rebotes ofensivos sobre los disponibles (incluidos los de equipo)'),
    num('drb_pct', 'DRB%', 'Rebotes defensivos sobre los disponibles (incluidos los de equipo)'),
    num('ftr', 'FTr', 'Tiros libres intentados por tiro de campo, en %'),
    num('fouls_per_game', 'Faltas', 'Faltas del equipo por partido en el periodo'),
  ]
}

export const PERIOD_KEYS = ['pts_per_game', 'opp_pts_per_game', 'ortg', 'drtg', 'net_rating', 'pace', 'efg_pct', 'tov_pct', 'orb_pct', 'drb_pct', 'ftr', 'fouls_per_game']
export const PERIOD_REVERSE = ['opp_pts_per_game', 'drtg', 'tov_pct', 'fouls_per_game']

// -- Situations ---------------------------------------------------------------

export type SituationTableRow = Record<string, number | string | null | undefined> & { team_id: string; team_name: string }

export function flattenSituations(rows: SituationRow[]): SituationTableRow[] {
  return rows.map(r => ({
    team_id: r.team_id, team_name: r.team_name, games: r.games, games_unreliable: r.games_unreliable,
    ato_own_n: r.ato_own.n, ato_own_ppp: r.ato_own.ppp, ato_rival_n: r.ato_rival.n, ato_rival_ppp: r.ato_rival.ppp,
    first_poss_n: r.first_poss.n, first_poss_ppp: r.first_poss.ppp,
    start_net: r.edges.start.net_rating, start_vs_rest: r.edges.start.vs_rest, start_tov_pct: r.edges.start.tov_pct,
    end_net: r.edges.end.net_rating, end_vs_rest: r.edges.end.vs_rest, end_tov_pct: r.edges.end.tov_pct,
  }))
}

export function situationColumns(): Col[] {
  const edge = (w: 'start' | 'end', label: string, when: string): Col => ({
    id: `grp_${w}`, header: label, columns: [
      num(`${w}_net`, 'Net', `Rating neto (por 100 posesiones) en ${when} de cada periodo`),
      num(`${w}_vs_rest`, 'vs resto', `Rating neto en ${when} menos el del resto del periodo`),
      num(`${w}_tov_pct`, 'TOV%', `% de posesiones acabadas en pérdida en ${when}`),
    ],
  })
  return [
    teamCol, games, excluded,
    { id: 'grp_ato_own', header: 'Tras su tiempo muerto', columns: [
      num('ato_own_n', 'N', 'Posesiones tras un tiempo muerto pedido por el equipo', 0),
      num('ato_own_ppp', 'PPP', 'Puntos por posesión tras un tiempo muerto del propio equipo', 2),
    ] },
    { id: 'grp_ato_rival', header: 'Tras el del rival', columns: [
      num('ato_rival_n', 'N', 'Posesiones tras un tiempo muerto pedido por el rival', 0),
      num('ato_rival_ppp', 'PPP', 'Puntos por posesión tras un tiempo muerto del rival', 2),
    ] },
    { id: 'grp_first', header: '1.ª del periodo', columns: [
      num('first_poss_n', 'N', 'Periodos que empezó con la posesión', 0),
      num('first_poss_ppp', 'PPP', 'Puntos por posesión en la primera posesión del periodo', 2),
    ] },
    edge('start', 'Primeros 2:00', 'los primeros 2:00'),
    edge('end', 'Últimos 2:00', 'los últimos 2:00'),
  ]
}

export const SITUATION_KEYS = ['ato_own_ppp', 'ato_rival_ppp', 'first_poss_ppp', 'start_net', 'start_vs_rest', 'start_tov_pct', 'end_net', 'end_vs_rest', 'end_tov_pct']
export const SITUATION_REVERSE = ['start_tov_pct', 'end_tov_pct']

// -- Timeouts -----------------------------------------------------------------

export type TimeoutTableRow = Record<string, number | string | null | undefined> & { team_id: string; team_name: string }

export function flattenTimeouts(rows: TimeoutRow[]): TimeoutTableRow[] {
  return rows.map(r => ({
    team_id: r.team_id, team_name: r.team_name,
    own_n: r.own.n, own_net_before: r.own.net_rating_before, own_net_after: r.own.net_rating_after, own_delta: r.own.delta_net_rating, own_pct: r.own.pct_caller_improves,
    rival_n: r.rival.n, rival_net_before: r.rival.net_rating_before, rival_net_after: r.rival.net_rating_after, rival_delta: r.rival.delta_net_rating, rival_pct: r.rival.pct_caller_improves,
  }))
}

export function timeoutColumns(): Col[] {
  const group = (w: 'own' | 'rival', label: string, by: string): Col => ({
    id: `grp_${w}`, header: label, columns: [
      num(`${w}_n`, 'N', `Tiempos muertos ${by} analizables (fuera los del último minuto y sin ventana completa)`, 0),
      num(`${w}_net_before`, 'Antes', `Rating neto del equipo en las 5 posesiones de cada equipo antes del tiempo muerto ${by}`),
      num(`${w}_net_after`, 'Después', `Rating neto del equipo en las 5 posesiones de cada equipo desde el tiempo muerto ${by}`),
      num(`${w}_delta`, 'Δ', `Cambio del rating neto del equipo tras el tiempo muerto ${by}`),
      num(`${w}_pct`, '% mejora', `% de tiempos muertos ${by} tras los que mejora ${w === 'own' ? 'el equipo' : 'el rival (quien lo pidió)'}`, 0, '%'),
    ],
  })
  return [teamCol, group('own', 'Pedidos por el equipo', 'pedidos por el equipo'), group('rival', 'Pedidos por el rival', 'pedidos por el rival')]
}

export const TIMEOUT_KEYS = ['own_net_before', 'own_net_after', 'own_delta', 'own_pct', 'rival_net_before', 'rival_net_after', 'rival_delta', 'rival_pct']
/** Lower is better when it is the rival who improves after calling the timeout. */
export const TIMEOUT_REVERSE = ['rival_pct']
