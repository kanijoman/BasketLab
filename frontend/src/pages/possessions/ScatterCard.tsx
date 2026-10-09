/** Scatter plots of the possessions page: team logos as dots (fallback: 3-letter abbreviation). */
import { useMemo, useState } from 'react'
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

import type { PossessionStat } from '@/api/client'
import { fmt } from '@/lib/utils'

function median(vals: number[]): number {
  if (!vals.length) return 0
  const sorted = [...vals].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

// -- Team logo scatter dot (FEB logo, fallback to 3-letter abbreviation) ------

export const FEB_LOGO = (id: string) => `https://imagenes.feb.es/imagen.aspx?i=${id}&ti=1`

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

export default function ScatterCard({ xKey, yKey, xLabel, yLabel, description, data, mode }: ScatterCardProps) {
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
            shape={(props: DotProps) => <TeamLogoDot {...props} />}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}
