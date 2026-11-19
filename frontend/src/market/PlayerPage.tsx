// The profile of a player of BasketLab Talent (B4, #880): his bio, his trajectory with the breakdown by competition and the radar of the percentiles of a row. The rules are in `player.ts`.
// The player is in the address (`/jugador/:personId`). His rows are in the files of the competitions: only those of his league are opened (a FEB id has no FBCYL rows), each one cached with the key
// the search uses, so coming from it costs nothing more. Percentiles are the player's in HIS competition and season: the page never compares competitions.
import { useMemo, useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Link, Navigate, useParams } from 'react-router-dom'
import type { ColumnDef } from '@tanstack/react-table'
import { ArrowLeft, Scale, UserRound } from 'lucide-react'
import Badge from '@/components/ui/Badge'
import Card from '@/components/ui/Card'
import DataTable from '@/components/ui/DataTable'
import EmptyState from '@/components/ui/EmptyState'
import { Field, Select } from '@/components/ui/Field'
import PageHeader from '@/components/ui/PageHeader'
import Spinner from '@/components/ui/Spinner'
import { loadCompetitionRows, loadIdentities, loadTalentCompetitions } from './data'
import { bioOf, personRows, radarAxes, trajectory, type BioField } from './player'
import PlayerPhoto from '@/components/ui/PlayerPhoto'
import { playerPhotoUrl } from '@/lib/playerPhoto'
import PlayerRadar from './PlayerRadar'
import PlayerZones from './PlayerZones'
import { toSearchRow, type SearchRow } from './search'

const dash = <span className="text-ink-faint" title="Sin dato">—</span>
const cell = (value: number | string | null | undefined) => (value === null || value === undefined || value === '' ? dash : value)
const label = (r: SearchRow) => `${r.season_label} · ${r.competition} · ${r.team_name}`
const keyOf = (r: SearchRow) => `${r.comp_key}|${r.team_id}`

function BioItem({ name, field, unit }: { name: string; field: BioField<string | number>; unit?: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-muted">{name}</dt>
      <dd className="text-sm font-medium text-ink">
        {field.value === null ? dash : `${field.value}${unit ?? ''}`}
        {field.from && <span className="ml-1 text-xs font-normal text-ink-muted" title={`Dato de otra temporada o equipo (${field.from})`}>(de otra ficha)</span>}
      </dd>
    </div>
  )
}

type Line = SearchRow & { change: string | null; origin: string | null }

const columns: ColumnDef<Line, unknown>[] = [
  { id: 'season', header: 'Temporada', accessorFn: r => r.season_label, size: 100 },
  { id: 'competition', header: 'Competición', accessorFn: r => r.competition, size: 190 },
  { id: 'team', header: 'Equipo', accessorFn: r => r.team_name, cell: c => (c.row.original.origin ? <>{c.row.original.team_name} <Badge tone="neutral">{c.row.original.origin}</Badge></> : c.row.original.team_name), size: 230 },
  { id: 'age', header: 'Edad (31/12)', accessorFn: r => r.age ?? undefined, sortUndefined: 'last', cell: c => cell(c.row.original.age), size: 90 },
  { id: 'games', header: 'PJ', accessorFn: r => r.games, size: 55 },
  { id: 'minutes', header: 'Min', accessorFn: r => Math.round(r.minutes / 60), size: 65 },
  { id: 'pts40', header: 'Pts/40', accessorFn: r => r.per40?.pts ?? undefined, sortUndefined: 'last', cell: c => cell(c.row.original.per40?.pts.toFixed(1)), size: 75 },
  { id: 'ast40', header: 'Ast/40', accessorFn: r => r.per40?.ast ?? undefined, sortUndefined: 'last', cell: c => cell(c.row.original.per40?.ast.toFixed(1)), size: 75 },
  { id: 'reb40', header: 'Reb/40', accessorFn: r => (r.per40 ? r.per40.orb + r.per40.drb : undefined), sortUndefined: 'last', cell: c => cell(c.row.original.per40 ? (c.row.original.per40.orb + c.row.original.per40.drb).toFixed(1) : null), size: 75 },
  { id: 'change', header: 'Cambio', enableSorting: false, cell: c => (c.row.original.change === 'competition' ? <Badge tone="accent">Cambia de competición</Badge> : c.row.original.change === 'team' ? <Badge tone="secondary">Cambia de equipo</Badge> : null), size: 160 },
]

const Shell = ({ children }: { children: React.ReactNode }) => <div className="mx-auto w-full max-w-5xl space-y-4 p-4 sm:p-6">{children}</div>
const Back = () => <Link to="/" className="inline-flex items-center gap-1 text-sm font-medium text-accent-text hover:underline"><ArrowLeft className="h-4 w-4" aria-hidden="true" />Volver al buscador</Link>

export default function PlayerPage() {
  const { personId = '' } = useParams()
  const league = personId.startsWith('fbcyl:') ? 'fbcyl' : 'feb'
  const manifest = useQuery({ queryKey: ['talent-competitions'], queryFn: loadTalentCompetitions })
  const identities = useQuery({ queryKey: ['talent-identities'], queryFn: loadIdentities })
  // a FEB person has his FEB rows and the FBCYL competitions that hold rows linked to him (`identities`); a FBCYL one, only FBCYL (unless she is linked: she is redirected below)
  const entries = useMemo(() => (manifest.data ?? []).filter(e => e.league === league || (identities.data?.by_feb[personId] ?? []).includes(e.key)), [manifest.data, league, identities.data, personId])
  const loaded = useQueries({ queries: entries.map(e => ({ queryKey: ['talent-rows', e.key], queryFn: () => loadCompetitionRows(e.key) })) })
  const failed = entries.filter((_, i) => loaded[i]?.isError).map(e => e.competition_label ?? e.competition)
  const mine = useMemo(() => personRows(loaded.flatMap((q, i) => (q.data ? q.data.rows.map(r => toSearchRow(entries[i], r)) : [])), personId),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [loaded.map(q => q.dataUpdatedAt).join(), entries, personId])
  const seasons = useMemo(() => trajectory(mine), [mine])
  const bio = useMemo(() => bioOf(mine), [mine])
  const [picked, setPicked] = useState<string | null>(null)

  const feb = identities.data?.links[personId]
  if (feb) return <Navigate to={`/jugador/${encodeURIComponent(feb)}`} replace />
  if (manifest.isLoading || identities.isLoading || (manifest.isSuccess && loaded.some(q => q.isLoading))) {
    return <div className="flex flex-col items-center gap-2 p-12"><Spinner size="lg" label="Cargando la ficha" /><p className="text-sm text-ink-muted">Cargando competiciones ({loaded.filter(q => !q.isLoading).length}/{entries.length})</p></div>
  }
  if (manifest.isError || (manifest.data ?? []).length === 0) {
    return <Shell><Back /><EmptyState icon={UserRound} title="Aún no hay datos de jugadores publicados" description="La ficha aparece aquí en cuanto se publique el primer conjunto de datos." /></Shell>
  }
  if (mine.length === 0) {
    return <Shell><Back /><EmptyState icon={UserRound} title="No encontramos a este jugador" description="El enlace no corresponde a ningún jugador de los datos publicados." /></Shell>
  }
  const options = [...seasons].reverse().flatMap(s => s.rows)
  const main = seasons[seasons.length - 1].main
  const row = options.find(r => keyOf(r) === picked) ?? main
  const lines: Line[] = seasons.flatMap(s => s.rows.map(r => ({ ...r, change: r === s.main ? s.change : null, origin: r.person_id !== personId ? 'Enlazada de FBCYL' : null })))
  const axes = radarAxes(row)
  return (
    <Shell>
      <Back />
      <div className="flex items-center gap-4">
        <PlayerPhoto name={bio.name} src={playerPhotoUrl(personId)} size={72} />
        <PageHeader className="min-w-0 flex-1" title={bio.name} subtitle={`${main.team_name} · ${main.competition} · ${main.season_label}`} />
      </div>
      <Link to={`/comparar?j=${encodeURIComponent(personId)}`} className="inline-flex items-center gap-1 text-sm font-medium text-accent-text hover:underline"><Scale className="h-4 w-4" aria-hidden="true" />Comparar con otros jugadores</Link>
      {failed.map(name => <p key={name} role="alert" className="text-sm text-bad">No se ha podido abrir {name}: la ficha puede estar incompleta.</p>)}
      <Card title="Datos personales">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          <BioItem name="Edad (31/12)" field={{ value: main.age, from: null }} />
          <BioItem name="Nacimiento" field={bio.birth} />
          <BioItem name="Altura" field={bio.height} unit=" cm" />
          <BioItem name="Posición" field={bio.position} />
          <BioItem name={bio.nationalities.length > 1 ? 'Nacionalidades' : 'Nacionalidad'} field={{ value: bio.nationalities.length ? bio.nationalities.join(' · ') : bio.nationality.value, from: bio.nationality.from }} />
        </dl>
        {bio.birthConflict && <p role="status" className="mt-3 text-xs text-warn">Las fuentes no coinciden en la fecha de nacimiento: conviene revisarla.</p>}
      </Card>
      <Card title="Trayectoria y desglose por competición" padding="none">
        <DataTable columns={columns} data={lines} searchable={false} ariaLabel="Trayectoria por temporada y competición" emptyMessage="Sin temporadas." />
      </Card>
      <Card title="Perfil">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-3">
            <Field label="Perfil de">
              <Select value={keyOf(row)} onChange={e => setPicked(e.target.value)} options={options.map(r => ({ value: keyOf(r), label: label(r) }))} />
            </Field>
            <p className="text-xs text-ink-muted">Percentil del jugador entre los de su competición y temporada; nunca se compara entre competiciones.</p>
            {!row.eligible && <Badge tone="warn">Pocos minutos: percentiles orientativos</Badge>}
            <ul aria-label="Percentiles" className="space-y-1 text-sm">
              {axes.map(a => <li key={a.key} className="flex justify-between gap-3"><span className="text-ink-muted">{a.label}</span><span className="font-medium text-ink">{a.value === null ? dash : Math.round(a.value)}</span></li>)}
            </ul>
          </div>
          <PlayerRadar axes={axes} name={bio.name} />
        </div>
      </Card>
      <PlayerZones row={row} />
    </Shell>
  )
}
