// The search of BasketLab Talent (B3, #879): filters over the players of the competitions of a season, a table and its CSV. The season, the competitions and the filters live in
// the address (shareable); the rules are in `search.ts`. It starts on the latest season published with its competitions.
import { useMemo } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import type { ColumnDef } from '@tanstack/react-table'
import { Search } from 'lucide-react'
import DataTable from '@/components/ui/DataTable'
import EmptyState from '@/components/ui/EmptyState'
import PageHeader from '@/components/ui/PageHeader'
import Spinner from '@/components/ui/Spinner'
import { loadCompetitionRows, loadTalentCompetitions, type TalentCompetitionEntry } from './data'
import SearchFiltersPanel from './SearchFiltersPanel'
import { ageOn1231, applySearch, csvOf, defaultSearch, filtersFromParams, filtersToParams, MAX_AUTO_COMPETITIONS, METRICS, type SearchRow } from './search'

const dash = <span className="text-ink-faint" title="Sin dato">—</span>
const cell = (value: number | string | null | undefined) => (value === null || value === undefined || value === '' ? dash : value)

function columns(many: boolean, metric: string): ColumnDef<SearchRow, unknown>[] {
  const cols: ColumnDef<SearchRow, unknown>[] = [
    { id: 'name', header: 'Jugador', accessorFn: r => r.full_name ?? r.name, size: 190 },
    { id: 'team', header: 'Equipo', accessorFn: r => r.team_name, size: 170 },
    ...(many ? [{ id: 'competition', header: 'Competición', accessorFn: (r: SearchRow) => r.competition, size: 150 }] : []),
    { id: 'age', header: 'Edad (31/12)', accessorFn: r => r.age ?? undefined, sortUndefined: 'last', cell: c => cell(c.row.original.age), size: 90 },
    { id: 'height', header: 'Altura', accessorFn: r => r.height ?? undefined, sortUndefined: 'last', cell: c => cell(c.row.original.height), size: 80 },
    { id: 'position', header: 'Posición', accessorFn: r => r.position ?? r.position_group ?? undefined, sortUndefined: 'last', cell: c => cell(c.row.original.position ?? c.row.original.position_group), size: 110 },
    { id: 'games', header: 'PJ', accessorFn: r => r.games, size: 55 },
    { id: 'minutes', header: 'Min', accessorFn: r => Math.round(r.minutes / 60), size: 65 },
    { id: 'pts40', header: 'Pts/40', accessorFn: r => r.per40?.pts ?? undefined, sortUndefined: 'last', cell: c => cell(c.row.original.per40?.pts.toFixed(1)), size: 75 },
    { id: 'ast40', header: 'Ast/40', accessorFn: r => r.per40?.ast ?? undefined, sortUndefined: 'last', cell: c => cell(c.row.original.per40?.ast.toFixed(1)), size: 75 },
  ]
  if (metric) {
    const key = metric as keyof NonNullable<SearchRow['pct']>
    cols.push({ id: 'pct', header: `Percentil ${METRICS.find(m => m.key === metric)?.label ?? metric}`, accessorFn: r => r.pct?.[key] ?? undefined, sortUndefined: 'last', cell: c => cell(c.row.original.pct?.[key]), size: 120 })
  }
  return cols
}

const withCompetition = (entry: TalentCompetitionEntry, rows: Awaited<ReturnType<typeof loadCompetitionRows>>['rows']): SearchRow[] =>
  rows.map(r => ({ ...r, comp_key: entry.key, competition: entry.competition, season: entry.season, season_label: entry.season_label, gender: entry.gender, level: entry.level, age: ageOn1231(r.birth, entry.season) }))

export default function SearchPage() {
  const [params, setParams] = useSearchParams()
  const manifest = useQuery({ queryKey: ['talent-competitions'], queryFn: loadTalentCompetitions })
  const entries = useMemo(() => manifest.data ?? [], [manifest.data])
  const start = useMemo(() => defaultSearch(entries), [entries])
  const season = params.get('s') ?? start.season
  const ofSeason = useMemo(() => entries.filter(e => e.season === season), [entries, season])
  const chosen = params.has('c') ? (params.get('c') ?? '').split(',').filter(k => ofSeason.some(e => e.key === k)) : ofSeason.length > MAX_AUTO_COMPETITIONS ? [] : ofSeason.map(e => e.key)
  const filters = useMemo(() => filtersFromParams(params), [params])
  const update = (patch: Record<string, string | null>, filtersNext = filters) => {
    const next = filtersToParams(filtersNext)
    for (const key of ['s', 'c']) if (params.has(key)) next.set(key, params.get(key)!)
    for (const [k, v] of Object.entries(patch)) { if (v === null) next.delete(k); else next.set(k, v) }
    setParams(next, { replace: true })
  }
  const loaded = useQueries({ queries: chosen.map(key => ({ queryKey: ['talent-rows', key], queryFn: () => loadCompetitionRows(key) })) })
  const failed = chosen.filter((_, i) => loaded[i]?.isError).map(k => ofSeason.find(e => e.key === k)?.competition ?? k)
  const loading = loaded.some(q => q.isLoading)
  const all = useMemo(() => loaded.flatMap((q, i) => (q.data ? withCompetition(ofSeason.find(e => e.key === chosen[i])!, q.data.rows) : [])),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [loaded.map(q => q.dataUpdatedAt).join(), chosen.join(), ofSeason])
  const result = useMemo(() => applySearch(all, filters), [all, filters])
  const csv = useMemo(() => csvOf(result.rows), [result.rows])
  const seasons = [...new Map(entries.map(e => [e.season, e.season_label])).entries()].sort((a, b) => Number(b[0]) - Number(a[0])).map(([value, label]) => ({ value, label }))
  const unavailable = manifest.isError || (manifest.isSuccess && entries.length === 0)

  if (manifest.isLoading) return <div className="flex justify-center p-12"><Spinner size="lg" label="Cargando competiciones" /></div>
  const header = <PageHeader title="Buscador de jugadores" subtitle="Jugadores y jugadoras de cualquier edad y competición; la edad es la del 31/12 del año en que empieza la temporada" />
  return (
    <div className="mx-auto w-full max-w-7xl space-y-4 p-4 sm:p-6">
      {header}
      {unavailable ? (
        <EmptyState icon={Search} title="Aún no hay datos de jugadores publicados" description="El buscador aparece aquí en cuanto se publique el primer conjunto de datos." />
      ) : (
        <>
          <SearchFiltersPanel seasons={seasons} season={season} onSeason={s => update({ s, c: null }, filters)} competitions={ofSeason} chosen={chosen}
            onChosen={keys => update({ c: keys.join(',') })} filters={filters} onFilters={next => update({}, next)} />
          {failed.map(name => <p key={name} role="alert" className="text-sm text-bad">No se ha podido abrir {name}. Prueba de nuevo más tarde.</p>)}
          <p className="text-sm text-ink-muted" aria-live="polite">
            {loading ? 'Cargando jugadores…' : `${result.rows.length} ${result.rows.length === 1 ? 'jugador encontrado' : 'jugadores encontrados'}`}
          </p>
          {!loading && result.hidden.total > 0 && (
            <p className="text-xs text-ink-muted">
              {result.hidden.total} {result.hidden.total === 1 ? 'jugador oculto' : 'jugadores ocultos'} por no tener el dato:{' '}
              <span data-testid="hidden-detail">
                {([['edad', result.hidden.age], ['altura', result.hidden.height], ['posición', result.hidden.position], ['percentil', result.hidden.metric]] as const).filter(([, n]) => n > 0).map(([name, n]) => `${name} (${n})`).join(', ')}
              </span>. Marca «Incluir los que no tienen el dato» para verlos.
            </p>
          )}
          <DataTable columns={columns(chosen.length > 1, filters.metric)} data={result.rows} loading={loading} searchable={false} ariaLabel="Jugadores encontrados"
            emptyMessage="Ningún jugador cumple los filtros." exportOptions={{ filename: `talent-${season}`, csvData: csv.data, csvHeaders: csv.headers }} />
        </>
      )}
    </div>
  )
}
