/**
 * PossessionsPage
 * Tabla de ritmo/eficiencia con cuartiles + scatter Ritmo × OER + scatter % Rápidas × OER Rápidas.
 * Los scatter muestran el logo FEB de cada equipo (fallback: abreviatura 3 letras).
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Label,
} from 'recharts'
import { Activity } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getPossessionStats, getTeamConsistency, type PossessionStat, type CVMap } from '@/api/client'
import { fmt } from '@/lib/utils'
import PageTransition from '@/components/ui/PageTransition'
import DataTable, { type QuartileMap } from '@/components/ui/DataTable'
import CVBadge from '@/components/ui/CVBadge'
import { tippedHeader } from '@/components/ui/Tooltip'

// -- Column definitions -------------------------------------------------------

function numCol(
  key: string,
  header: string,
  decimals = 1,
  cv: CVMap | null = null,
): ColumnDef<PossessionStat, unknown> {
  return {
    id: key,
    accessorKey: key,
    header: tippedHeader(header),
    cell: ({ getValue, row }) => {
      const v = getValue() as number
      const formatted = fmt(v, decimals)
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
function numColOpt(key: string, header: string, decimals = 1): ColumnDef<PossessionStat, unknown> {
  return {
    id: key,
    accessorKey: key,
    header: tippedHeader(header),
    cell: ({ getValue }) => {
      const v = getValue() as number | null | undefined
      if (v == null) return <span className="text-ink-disabled">—</span>
      return fmt(v, decimals)
    },
  }
}

function buildCols(cv: CVMap | null): ColumnDef<PossessionStat, unknown>[] {
  return [
    {
      id: 'team_name',
      accessorKey: 'team_name',
      header: 'Equipo',
      cell: ({ getValue }) => (
        <span className="font-medium text-ink-primary whitespace-nowrap">{getValue() as string}</span>
      ),
    },
    numCol('total_games',          'PJ',    0),
    numCol('possessions_per_game', 'Pos/P', 1, cv),
    numCol('pace',                 'Ritmo', 1, cv),
    numCol('oer',                  'OER',   1, cv),
    numCol('der',                  'DER',   1, cv),
    numCol('net_rating',           'Net',   1, cv),
    // Play-by-play derived columns
    numColOpt('avg_duration',             'Tpo. Pos. (s)', 1),
    numColOpt('pct_fast',                 '% Rápidas',    1),
    numColOpt('pct_medium',               '% Medias',     1),
    numColOpt('pct_slow',                 '% Lentas',     1),
    numColOpt('oer_fast',                 'OER Rápidas',  1),
    numColOpt('oer_medium',               'OER Medias',   1),
    numColOpt('oer_slow',                 'OER Lentas',   1),
    numColOpt('est_possessions_per_game', 'Est. Pos/40',  1),
  ]
}

const REVERSE_COLS = ['der', 'pct_slow']

// -- Quartile computation from data (no separate endpoint for possessions) ----

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

function buildQuartileMap(data: PossessionStat[]): QuartileMap {
  const keys: (keyof PossessionStat)[] = [
    'possessions_per_game', 'pace', 'oer', 'der', 'net_rating',
    'avg_duration', 'pct_fast', 'pct_medium', 'pct_slow',
    'oer_fast', 'oer_medium', 'oer_slow', 'est_possessions_per_game',
  ]
  const map: QuartileMap = {}
  keys.forEach(k => { map[k as string] = computeQuartiles(data, k) })
  return map
}

function median(vals: number[]): number {
  if (!vals.length) return 0
  const sorted = [...vals].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

// -- Team logo scatter dot (FEB logo, fallback to 3-letter abbreviation) ------

const FEB_LOGO = (id: string) => `https://imagenes.feb.es/imagen.aspx?i=${id}&ti=1`

interface DotProps {
  cx?: number
  cy?: number
  payload?: PossessionStat
}

function TeamLogoDot({ cx = 0, cy = 0, payload }: DotProps) {
  const [imgError, setImgError] = useState(false)
  if (!payload) return null

  const teamId = payload.team_id
  const initials = (payload.team_name ?? '').split(' ').filter(Boolean).slice(-1)[0]?.slice(0, 3).toUpperCase() ?? '?'
  const r = 13

  if (!teamId || imgError) {
    return (
      <g>
        <circle cx={cx} cy={cy} r={r} fill="#1e3a5f" stroke="#3b82f6" strokeWidth={1} />
        <text x={cx} y={cy + 4} textAnchor="middle" fontSize={8} fill="#d1d5db" style={{ pointerEvents: 'none' }}>
          {initials}
        </text>
      </g>
    )
  }

  const clipId = `logo-clip-${teamId}`
  return (
    <g>
      <defs>
        <clipPath id={clipId}>
          <circle cx={cx} cy={cy} r={r} />
        </clipPath>
      </defs>
      <circle cx={cx} cy={cy} r={r} fill="#0f172a" stroke="#334155" strokeWidth={1} />
      <image
        href={FEB_LOGO(teamId)}
        x={cx - r} y={cy - r}
        width={r * 2} height={r * 2}
        clipPath={`url(#${clipId})`}
        onError={() => setImgError(true)}
      />
    </g>
  )
}

function CustomTooltip({
  active,
  payload,
  mode,
}: {
  active?: boolean
  payload?: Array<{ payload: PossessionStat }>
  mode: 'pace' | 'fast'
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  const teamId = d.team_id
  return (
    <div className="bg-surface-card border border-surface-border rounded-lg px-3 py-2 text-xs shadow-lg min-w-[140px]">
      <div className="flex items-center gap-2 mb-2">
        {teamId && (
          <img
            src={FEB_LOGO(teamId)}
            alt=""
            className="w-5 h-5 object-contain rounded-sm"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
          />
        )}
        <p className="font-semibold text-ink-primary leading-tight">{d.team_name}</p>
      </div>
      {mode === 'pace' ? (
        <>
          <p className="text-ink-secondary">Ritmo: <span className="text-ink-primary">{fmt(d.pace)}</span></p>
          <p className="text-ink-secondary">OER: <span className="text-ink-primary">{fmt(d.oer)}</span></p>
          <p className="text-ink-secondary">DER: <span className="text-ink-primary">{fmt(d.der)}</span></p>
          <p className="text-ink-secondary">Net: <span className="text-ink-primary">{fmt(d.net_rating)}</span></p>
        </>
      ) : (
        <>
          <p className="text-ink-secondary">% Rápidas: <span className="text-ink-primary">{d.pct_fast != null ? fmt(d.pct_fast) + '%' : '—'}</span></p>
          <p className="text-ink-secondary">OER Rápidas: <span className="text-ink-primary">{d.oer_fast != null ? fmt(d.oer_fast) : '—'}</span></p>
          <p className="text-ink-secondary">% Medias: <span className="text-ink-primary">{d.pct_medium != null ? fmt(d.pct_medium) + '%' : '—'}</span></p>
          <p className="text-ink-secondary">% Lentas: <span className="text-ink-primary">{d.pct_slow != null ? fmt(d.pct_slow) + '%' : '—'}</span></p>
        </>
      )}
    </div>
  )
}

// -- Reusable scatter card ----------------------------------------------------

interface ScatterCardProps {
  xKey: keyof PossessionStat
  yKey: keyof PossessionStat
  xLabel: string
  yLabel: string
  description: string
  data: PossessionStat[]
  mode: 'pace' | 'fast'
}

function ScatterCard({ xKey, yKey, xLabel, yLabel, description, data, mode }: ScatterCardProps) {
  const xVals = useMemo(
    () => data.map(d => d[xKey] as number).filter(v => v != null && !Number.isNaN(v)),
    [data, xKey],
  )
  const yVals = useMemo(
    () => data.map(d => d[yKey] as number).filter(v => v != null && !Number.isNaN(v)),
    [data, yKey],
  )
  const medX = useMemo(() => median(xVals), [xVals])
  const medY = useMemo(() => median(yVals), [yVals])

  return (
    <div className="card p-4">
      <p className="text-sm text-ink-secondary mb-4">{description}</p>
      <div className="grid grid-cols-2 gap-1 text-xs mb-3 max-w-sm ml-auto mr-0">
        <span className="text-right text-yellow-500">Rápido + Eficiente →</span>
        <span className="text-green-500">← Rápido – Ineficiente</span>
        <span className="text-red-400">Lento + Eficiente →</span>
        <span className="text-ink-secondary">← Lento – Ineficiente</span>
      </div>
      <ResponsiveContainer width="100%" height={420}>
        <ScatterChart margin={{ top: 10, right: 30, bottom: 30, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            type="number" dataKey={xKey as string} name={xLabel}
            domain={['auto', 'auto']}
            tick={{ fontSize: 11, fill: '#6b7280' }}
          >
            <Label value={xLabel} position="insideBottom" offset={-15} fontSize={11} fill="#6b7280" />
          </XAxis>
          <YAxis
            type="number" dataKey={yKey as string} name={yLabel}
            domain={['auto', 'auto']}
            tick={{ fontSize: 11, fill: '#6b7280' }}
            width={45}
          >
            <Label value={yLabel} angle={-90} position="insideLeft" fontSize={11} fill="#6b7280" />
          </YAxis>
          <Tooltip content={<CustomTooltip mode={mode} />} />
          {medX > 0 && <ReferenceLine x={medX} stroke="#555" strokeDasharray="5 4" />}
          {medY > 0 && <ReferenceLine y={medY} stroke="#555" strokeDasharray="5 4" />}
          <Scatter
            data={data}
            // @ts-ignore — recharts shape prop accepts render function
            shape={(props: DotProps) => <TeamLogoDot {...props} />}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

// -- Component ----------------------------------------------------------------

type Tab = 'table' | 'scatter' | 'scatter2'

export default function PossessionsPage() {
  const { collection } = useCollection()
  const [tab, setTab] = useState<Tab>('table')

  const { data: stats = [], isLoading } = useQuery<PossessionStat[]>({
    queryKey: ['possessions', collection?.name],
    queryFn: () => getPossessionStats(collection!.name),
    enabled: Boolean(collection),
    staleTime: 5 * 60_000,
  })

  const { data: consistencyRaw } = useQuery({
    queryKey:  ['team-consistency-v2', collection?.name],
    queryFn:   () => getTeamConsistency(collection!.name),
    enabled:   Boolean(collection),
    staleTime: 30 * 60_000,
  })
  const consistencyByName: CVMap | null = consistencyRaw?.own ?? null

  const cols = useMemo(() => buildCols(consistencyByName), [consistencyByName])
  const quartileMap = useMemo(() => buildQuartileMap(stats), [stats])

  // Fast-possession scatter — filter teams without PBP data
  const statsWithPBP = useMemo(
    () => stats.filter(d => d.pct_fast != null && d.oer_fast != null),
    [stats],
  )

  const TABS: [Tab, string][] = [
    ['table',    'Tabla'],
    ['scatter',  'Scatter Ritmo × OER'],
    ['scatter2', 'Scatter % Rápidas × OER'],
  ]

  return (
    <PageTransition>
      <div className="space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h1 className="text-2xl font-bold text-ink-primary">Análisis de Posesiones</h1>
            <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
          </div>
          {/* Tab toggle */}
          <div className="flex rounded-lg overflow-hidden border border-surface-border text-sm">
            {TABS.map(([key, lbl]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-4 py-1.5 font-medium transition-colors ${
                  tab === key ? 'bg-accent-500 text-white' : 'text-ink-secondary hover:bg-surface-hover'
                }`}
              >
                {lbl}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="card p-16 flex justify-center">
            <div className="w-8 h-8 border-2 border-accent-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : stats.length === 0 ? (
          <div className="card p-10 flex flex-col items-center gap-3 text-center">
            <Activity className="w-10 h-10 text-accent-400 opacity-40" />
            <p className="text-ink-secondary text-sm">Sin datos de posesiones para esta colección</p>
          </div>
        ) : tab === 'table' ? (
          <DataTable
            columns={cols}
            data={stats}
            quartiles={quartileMap}
            reverseColumns={REVERSE_COLS}
            searchable
            searchPlaceholder="Buscar equipo…"
            exportOptions={{ filename: `posesiones_${collection?.name}` }}
          />
        ) : tab === 'scatter' ? (
          <ScatterCard
            xKey="pace"
            yKey="oer"
            xLabel="Ritmo (pos/P)"
            yLabel="OER"
            description="Ritmo (posesiones/partido) × OER (eficiencia ofensiva · pts/100 pos.) — líneas discontinuas = mediana de la liga"
            data={stats}
            mode="pace"
          />
        ) : (
          <ScatterCard
            xKey="pct_fast"
            yKey="oer_fast"
            xLabel="% Posesiones Rápidas (≤8s)"
            yLabel="OER Rápidas"
            description="% de posesiones rápidas (≤8s) × eficiencia ofensiva en esas posesiones — líneas discontinuas = mediana de la liga"
            data={statsWithPBP}
            mode="fast"
          />
        )}
      </div>
    </PageTransition>
  )
}
