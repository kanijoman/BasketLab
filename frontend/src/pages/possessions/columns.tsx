/**
 * Column definitions of the possessions table, split in three views so each one fits without
 * horizontal scroll: summary (pace / efficiency), own style (fast / medium / slow) and rival.
 */
import type { ColumnDef } from '@tanstack/react-table'
import type { CVMap, PossessionStat } from '@/api/client'
import CVBadge from '@/components/ui/CVBadge'
import Tooltip, { tippedHeader } from '@/components/ui/Tooltip'
import type { QuartileMap } from '@/components/ui/DataTable'
import { fmt } from '@/lib/utils'
import { FEB_LOGO } from './ScatterCard'

export type PossessionView = 'summary' | 'own' | 'rival'

export const VIEWS: { key: PossessionView; label: string }[] = [
  { key: 'summary', label: 'Resumen' },
  { key: 'own', label: 'Estilo propio' },
  { key: 'rival', label: 'Rival' },
]

type Col = ColumnDef<PossessionStat, unknown>

export const TEAM_COLUMN_SIZE = 240
export const NUMERIC_COLUMN_SIZE = 64

// -- Cells --------------------------------------------------------------------

function TeamCell({ name, teamId }: { name: string; teamId?: string }) {
  return (
    <span className="flex items-center gap-2 min-w-0">
      {teamId && (
        <img
          src={FEB_LOGO(teamId)}
          alt=""
          className="w-5 h-5 shrink-0 object-contain rounded-sm"
          onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
        />
      )}
      {/* wraps up to two lines and always keeps the full name in the tooltip: it is never cut silently */}
      <span title={name} className="font-medium text-ink-primary leading-tight line-clamp-2 break-words">{name}</span>
    </span>
  )
}

const teamCol: Col = {
  id: 'team_name',
  accessorKey: 'team_name',
  header: 'Equipo',
  size: TEAM_COLUMN_SIZE,
  cell: ({ getValue, row }) => (
    <TeamCell name={getValue() as string} teamId={(row.original as PossessionStat).team_id} />
  ),
}

function numCol(key: string, header: string, decimals = 1, cv: CVMap | null = null): Col {
  return {
    id: key,
    accessorKey: key,
    header: tippedHeader(header),
    cell: ({ getValue, row }) => {
      const formatted = fmt(getValue() as number, decimals)
      const cvEntry = cv?.[(row.original as PossessionStat).team_name]?.[key]
      if (!cvEntry) return formatted
      return (
        <span className="inline-flex items-center gap-1.5">
          <span>{formatted}</span>
          <CVBadge entry={cvEntry} />
        </span>
      )
    },
  }
}

/** Column for nullable numeric fields — shows em dash when value is null/undefined. */
function numColOpt(key: string, header: string | (() => JSX.Element), decimals = 1): Col {
  return {
    id: key,
    accessorKey: key,
    header: typeof header === 'string' ? tippedHeader(header) : header,
    cell: ({ getValue }) => {
      const v = getValue() as number | null | undefined
      if (v == null) return <span className="text-ink-disabled">—</span>
      return fmt(v, decimals)
    },
  }
}

/** Short sub-header ("%" / "OER") whose tooltip says what it measures for its group. */
function subHeader(short: string, description: string): () => JSX.Element {
  return () => (
    <Tooltip text={description}>
      <span className="underline decoration-dotted underline-offset-2">{short}</span>
    </Tooltip>
  )
}

// -- Views --------------------------------------------------------------------

const KINDS = [
  { id: 'fast', group: 'Rápidas', what: 'rápidas (≤ 8 s)' },
  { id: 'medium', group: 'Medias', what: 'medias' },
  { id: 'slow', group: 'Lentas', what: 'lentas' },
] as const

/** Rápidas / Medias / Lentas, each with its share of possessions (%) and its OER. */
function styleGroups(prefix: '' | 'rival_'): Col[] {
  const owner = prefix ? ' del rival' : ''
  return KINDS.map(k => ({
    id: `${prefix}grp_${k.id}`,
    header: k.group,
    columns: [
      numColOpt(`${prefix}pct_${k.id}`, subHeader('%', `% de posesiones ${k.what}${owner}`)),
      numColOpt(`${prefix}oer_${k.id}`, subHeader('OER', `Puntos por 100 posesiones ${k.what}${owner}`)),
    ],
  }))
}

function summaryCols(cv: CVMap | null): Col[] {
  return [
    teamCol,
    numCol('total_games', 'PJ', 0),
    numCol('possessions_per_game', 'Pos/P', 1, cv),
    numCol('pace', 'Ritmo', 1, cv),
    numCol('oer', 'OER', 1, cv),
    numCol('der', 'DER', 1, cv),
    numCol('net_rating', 'Net', 1, cv),
  ]
}

function ownCols(): Col[] {
  return [
    teamCol,
    numColOpt('avg_duration', 'Tpo. Pos. (s)'),
    numColOpt('est_possessions_per_game', 'Est. Pos/40'),
    ...styleGroups(''),
  ]
}

function rivalCols(): Col[] {
  return [
    teamCol,
    numColOpt('rival_avg_duration', 'Tpo. Pos. Rival (s)'),
    numColOpt('rival_pace_differential', 'Δ Ritmo Rival (s)'),
    ...styleGroups('rival_'),
  ]
}

export function buildCols(view: PossessionView, cv: CVMap | null): Col[] {
  if (view === 'own') return ownCols()
  if (view === 'rival') return rivalCols()
  return summaryCols(cv)
}

// -- CSV (all the columns, whatever the view) ----------------------------------

const CSV_LABELS: [string, string][] = [
  ['team_name', 'Equipo'], ['total_games', 'PJ'], ['possessions_per_game', 'Pos/P'], ['pace', 'Ritmo'],
  ['oer', 'OER'], ['der', 'DER'], ['net_rating', 'Net'],
  ['avg_duration', 'Tpo. Pos. (s)'], ['est_possessions_per_game', 'Est. Pos/40'],
  ['pct_fast', '% Rápidas'], ['pct_medium', '% Medias'], ['pct_slow', '% Lentas'],
  ['oer_fast', 'OER Rápidas'], ['oer_medium', 'OER Medias'], ['oer_slow', 'OER Lentas'],
  ['rival_avg_duration', 'Tpo. Pos. Rival (s)'], ['rival_pace_differential', 'Δ Ritmo Rival (s)'],
  ['rival_pct_fast', '% Rápidas Rival'], ['rival_pct_medium', '% Medias Rival'], ['rival_pct_slow', '% Lentas Rival'],
  ['rival_oer_fast', 'OER Rápidas Rival'], ['rival_oer_medium', 'OER Medias Rival'], ['rival_oer_slow', 'OER Lentas Rival'],
]

export const ALL_VIEW_KEYS: string[] = CSV_LABELS.map(([key]) => key)

export function csvColumns(): { label: string; key: string }[] {
  return CSV_LABELS.map(([key, label]) => ({ key, label }))
}

// -- Colours -------------------------------------------------------------------

export const REVERSE_COLS = ['der', 'pct_slow', 'rival_pct_slow', 'rival_oer_fast', 'rival_oer_medium', 'rival_oer_slow', 'rival_pace_differential']

function computeQuartiles(data: PossessionStat[], key: keyof PossessionStat): [number, number, number] {
  const vals = data
    .map(d => Number(d[key]))
    .filter(v => !Number.isNaN(v) && v !== 0)
    .sort((a, b) => a - b)
  if (vals.length < 4) return [0, 0, 0]
  const q = (p: number) => {
    const idx = (vals.length - 1) * p
    const lo = Math.floor(idx)
    const hi = Math.ceil(idx)
    return vals[lo] + (vals[hi] - vals[lo]) * (idx - lo)
  }
  return [q(0.25), q(0.5), q(0.75)]
}

export function buildQuartileMap(data: PossessionStat[]): QuartileMap {
  const map: QuartileMap = {}
  ALL_VIEW_KEYS.filter(k => k !== 'team_name' && k !== 'total_games').forEach(k => {
    map[k] = computeQuartiles(data, k as keyof PossessionStat)
  })
  return map
}
