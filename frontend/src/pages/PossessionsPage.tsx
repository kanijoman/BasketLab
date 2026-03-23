/**
 * PossessionsPage — Fase 3
 * Tabla de ritmo/eficiencia con cuartiles + scatter Ritmo × OER con 4 cuadrantes.
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
  ]
}

const REVERSE_COLS = ['der']

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
  const keys: (keyof PossessionStat)[] = ['possessions_per_game', 'pace', 'oer', 'der', 'net_rating']
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

// -- Custom scatter dot with team label ---------------------------------------

interface DotProps {
  cx?: number
  cy?: number
  payload?: PossessionStat
}

function TeamDot({ cx = 0, cy = 0, payload }: DotProps) {
  if (!payload) return null
  return (
    <g>
      <circle cx={cx} cy={cy} r={5} fill="#3b82f6" fillOpacity={0.85} stroke="#93c5fd" strokeWidth={1} />
      <text
        x={cx + 6} y={cy + 4}
        fontSize={9} fill="#d1d5db"
        style={{ pointerEvents: 'none' }}
      >
        {payload.team_name?.split(' ').slice(-1)[0]}
      </text>
    </g>
  )
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: PossessionStat }> }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-surface-card border border-surface-border rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-ink-primary mb-1">{d.team_name as string}</p>
      <p className="text-ink-secondary">Ritmo: <span className="text-ink-primary">{fmt(d.pace as number)}</span></p>
      <p className="text-ink-secondary">OER: <span className="text-ink-primary">{fmt(d.oer as number)}</span></p>
      <p className="text-ink-secondary">DER: <span className="text-ink-primary">{fmt(d.der as number)}</span></p>
      <p className="text-ink-secondary">Net: <span className="text-ink-primary">{fmt(d.net_rating as number)}</span></p>
    </div>
  )
}

// -- Component ----------------------------------------------------------------

export default function PossessionsPage() {
  const { collection } = useCollection()
  const [tab, setTab] = useState<'table' | 'scatter'>('table')

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

  // Scatter quadrant medians
  const paceVals = useMemo(() => stats.map(d => d.pace).filter(Boolean), [stats])
  const oerVals  = useMemo(() => stats.map(d => d.oer).filter(Boolean), [stats])
  const medPace  = useMemo(() => median(paceVals), [paceVals])
  const medOer   = useMemo(() => median(oerVals), [oerVals])

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
            {([['table', 'Tabla'], ['scatter', 'Scatter Ritmo × OER']] as const).map(([key, lbl]) => (
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
        ) : (
          /* Scatter chart */
          <div className="card p-4">
            <p className="text-sm text-ink-secondary mb-4">
              Ritmo (posesiones/partido) × OER (eficiencia ofensiva · pts/100 pos.)
              — líneas discontinuas = mediana de la liga
            </p>
            {/* Quadrant labels */}
            <div className="grid grid-cols-2 gap-1 text-xs text-ink-secondary mb-3 max-w-sm ml-auto mr-0">
              <span className="text-right text-yellow-500">Rápido + Eficiente →</span>
              <span className="text-green-500">← Rápido – Ineficiente</span>
              <span className="text-red-400">Lento + Eficiente →</span>
              <span className="text-ink-secondary">← Lento – Ineficiente</span>
            </div>
            <ResponsiveContainer width="100%" height={400}>
              <ScatterChart margin={{ top: 10, right: 30, bottom: 30, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis
                  type="number" dataKey="pace" name="Ritmo"
                  domain={['auto', 'auto']}
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                >
                  <Label value="Ritmo (pos/P)" position="insideBottom" offset={-15} fontSize={11} fill="#6b7280" />
                </XAxis>
                <YAxis
                  type="number" dataKey="oer" name="OER"
                  domain={['auto', 'auto']}
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                  width={45}
                >
                  <Label value="OER" angle={-90} position="insideLeft" fontSize={11} fill="#6b7280" />
                </YAxis>
                <Tooltip content={<CustomTooltip />} />
                {/* Quadrant reference lines at medians */}
                {medPace > 0 && (
                  <ReferenceLine x={medPace} stroke="#555" strokeDasharray="5 4" />
                )}
                {medOer > 0 && (
                  <ReferenceLine y={medOer} stroke="#555" strokeDasharray="5 4" />
                )}
                <Scatter
                  data={stats}
                  // @ts-ignore — recharts shape prop accepts render function
                  shape={(props: DotProps) => <TeamDot {...props} />}
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </PageTransition>
  )
}
