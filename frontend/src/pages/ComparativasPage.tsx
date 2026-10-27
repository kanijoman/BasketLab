/**
 * ComparativasPage — the comparative reports of the weekly report, on demand (issue #607).
 *
 * Home vs away, won vs lost, and a stretch of dates vs the rest of the season. Each cell is the figure of the first group with the REAL difference with the second
 * (issue #608: no arrows); green when it is good, red when it is bad. The view of the rivals swaps good and bad: what they did against a team is good for them.
 */
import { teamColumn } from '@/components/ui/TeamCell'
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'

import { useCollection } from '@/context/CollectionContext'
import { getTeamComparison, type ComparisonKind, type ComparisonRow, type TeamStat } from '@/api/client'
import { fmt, fmtPct, cn } from '@/lib/utils'
import { ADVANCED_COL_DEFS, BASIC_COL_DEFS, type ColDef } from '@/lib/teamColumns'
import { computeQuartileMap } from '@/lib/quartiles'
import PageTransition from '@/components/ui/PageTransition'
import DataTable from '@/components/ui/DataTable'
import DiffBadge from '@/components/ui/DiffBadge'
import { tippedHeader } from '@/components/ui/Tooltip'

const KINDS: { id: ComparisonKind; label: string }[] = [
  { id: 'venue', label: 'Local vs visitante' },
  { id: 'result', label: 'Ganados vs perdidos' },
  { id: 'period', label: 'Tramo vs resto' },
]

/** ``YYYY-MM-DD`` of the local day, ``daysBack`` days before today (the weekly report's «last 30 days» includes today: 29 days back). */
function isoDay(daysBack: number): string {
  const d = new Date()
  d.setDate(d.getDate() - daysBack)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

type Flat = Partial<TeamStat> & { team_name: string; games: string }

function Segmented<T extends string>({ value, options, onChange }: { value: T; options: { id: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="flex rounded-lg overflow-hidden border border-line">
      {options.map(o => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          className={cn('px-3 py-1.5 text-sm font-medium transition-colors', value === o.id ? 'bg-accent/30 text-accent-text' : 'text-ink-muted hover:bg-surface-raised hover:text-ink')}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function buildColumns(defs: ColDef[], byName: Record<string, ComparisonRow>, rivals: boolean): ColumnDef<Flat, unknown>[] {
  const cols: ColumnDef<Flat, unknown>[] = [
    teamColumn<Flat>(),
    { id: 'games', accessorKey: 'games', header: tippedHeader('PJ'), size: 60 },
  ]
  for (const def of defs.filter(d => !d.count)) {
    const { key, header, decimals = 1, pct = false, reverse = false, size = 60 } = def
    cols.push({
      id: key as string,
      accessorKey: key as string,
      size: size + 40,
      header: tippedHeader(header),
      cell: ({ getValue, row }) => {
        const v = getValue() as number | null | undefined
        const teamRow = byName[row.original.team_name]
        const other = (teamRow?.a ? teamRow.b?.[key] : null) as number | null | undefined      // a team with one group only has nothing to compare with
        return (
          <span className="inline-flex items-center gap-1.5">
            <span>{pct ? fmtPct(v) : fmt(v, decimals)}</span>
            <DiffBadge recent={v} season={other} reverse={reverse !== rivals} decimals={decimals} className="text-[10px]" />
          </span>
        )
      },
    })
  }
  return cols
}

export default function ComparativasPage() {
  const { collection } = useCollection()
  const [by, setBy] = useState<ComparisonKind>('venue')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [side, setSide] = useState<'team' | 'opponent'>('team')
  const [view, setView] = useState<'basic' | 'advanced'>('basic')

  const needsDates = by === 'period' && !from && !to
  const range = by === 'period' ? { ...(from ? { from } : {}), ...(to ? { to } : {}) } : undefined

  const { data, isLoading, isError } = useQuery({
    queryKey: ['team-comparison', collection?.name, by, from, to],
    queryFn: () => getTeamComparison(collection!.name, by, range),
    enabled: Boolean(collection) && !needsDates,
    staleTime: 5 * 60_000,
  })

  const rivals = side === 'opponent'
  const defs = view === 'advanced' ? ADVANCED_COL_DEFS : BASIC_COL_DEFS
  const rows = useMemo(() => (data ? data[side] : []), [data, side])
  const flat: Flat[] = useMemo(() => rows.map(r => ({ ...(r.a ?? r.b ?? {}), team_name: r.team_name, team_id: r.team_id ?? undefined, games: `${r.games_a}+${r.games_b}` })), [rows])
  const byName = useMemo(() => Object.fromEntries(rows.map(r => [r.team_name, r])), [rows])
  const columns = useMemo(() => buildColumns(defs, byName, rivals), [defs, byName, rivals])
  const quartiles = useMemo(() => computeQuartileMap(flat, defs.filter(d => !d.count).map(d => d.key as string)), [flat, defs])
  const reverseColumns = useMemo(() => defs.filter(d => d.reverse !== rivals).map(d => d.key as string), [defs, rivals])

  if (!collection) {
    return <PageTransition><p className="text-center text-ink-faint mt-16">Selecciona una colección para continuar.</p></PageTransition>
  }

  const shortcut = (days: number) => { setFrom(isoDay(days - 1)); setTo(isoDay(0)) }

  return (
    <PageTransition>
      <div className="space-y-4">
        <div>
          <h1 className="text-xl font-bold text-ink">Comparativas</h1>
          <p className="text-sm text-ink-faint mt-0.5">{collection.label}</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Segmented value={by} options={KINDS} onChange={setBy} />
          <Segmented value={side} options={[{ id: 'team', label: 'Equipos' }, { id: 'opponent', label: 'Rivales' }]} onChange={setSide} />
          <Segmented value={view} options={[{ id: 'basic', label: 'Básico' }, { id: 'advanced', label: 'Avanzado' }]} onChange={setView} />
        </div>

        {by === 'period' && (
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs text-ink-muted flex flex-col gap-1">Desde
              <input type="date" value={from} onChange={e => setFrom(e.target.value)} className="bg-canvas border border-line rounded px-2 py-1 text-sm text-ink" />
            </label>
            <label className="text-xs text-ink-muted flex flex-col gap-1">Hasta
              <input type="date" value={to} onChange={e => setTo(e.target.value)} className="bg-canvas border border-line rounded px-2 py-1 text-sm text-ink" />
            </label>
            <button onClick={() => shortcut(30)} className="px-3 py-1.5 text-sm rounded border border-line text-ink-muted hover:bg-surface-raised">Últimos 30 días</button>
            <button onClick={() => shortcut(15)} className="px-3 py-1.5 text-sm rounded border border-line text-ink-muted hover:bg-surface-raised">Últimos 15 días</button>
          </div>
        )}

        {needsDates && <p className="text-sm text-ink-faint">Elige un tramo (desde y/o hasta, o un atajo) para compararlo con el resto de la temporada.</p>}
        {isError && <p className="text-bad text-sm">Error al cargar los datos.</p>}

        {data && (
          <p className="text-xs text-ink-faint">
            {data.label_a} frente a {data.label_b}: cada celda es el valor de «{data.label_a}» y, al lado, su diferencia con «{data.label_b}»
            {rivals ? ' (lo que lograron los rivales: verde es bueno para ellos).' : ' (verde es mejor, rojo peor; en pérdidas, menos es mejor).'}
          </p>
        )}

        {!needsDates && (
          <DataTable
            columns={columns}
            data={flat}
            quartiles={quartiles}
            reverseColumns={reverseColumns}
            loading={isLoading}
            searchable
            searchPlaceholder="Buscar equipo…"
            exportOptions={{
              filename: `comparativa_${by}_${side}_${collection.name}`,
              pdfTitle: `Comparativa — ${KINDS.find(k => k.id === by)?.label}`,
              csvHeaders: columns.map(c => ({ key: String((c as { accessorKey?: string }).accessorKey ?? c.id ?? ''), label: typeof c.header === 'string' ? c.header : String((c as { accessorKey?: string }).accessorKey ?? c.id ?? '') })),
              csvData: flat,
            }}
          />
        )}
      </div>
    </PageTransition>
  )
}
