// «Mi equipo» of BasketLab Talent (C1, #882): the staff chooses a team of any competition and season, and the page says who its rotation is, where it has holes (position and profile) and gives the search that
// would fill each one, already filled in. The team is in the address (`?c=<competition>&e=<team>`) and, when the address says nothing, the one remembered in this browser. The rules are in `myTeam.ts`.
import { useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { Users } from 'lucide-react'
import Badge from '@/components/ui/Badge'
import Card from '@/components/ui/Card'
import EmptyState from '@/components/ui/EmptyState'
import { Field, Select } from '@/components/ui/Field'
import PageHeader from '@/components/ui/PageHeader'
import Spinner from '@/components/ui/Spinner'
import { loadCompetitionRows, loadTalentCompetitions } from './data'
import { ageMix, positionBalance, profileGaps, squadOf, suggestions, teamsOf, AGE_VETERAN, AGE_YOUNG, MIN_ROTATION } from './myTeam'
import { recallTeam, rememberTeam } from './myTeamMemory'
import { toSearchRow, type PositionGroup } from './search'

const GROUP_NAME: Record<PositionGroup, string> = { G: 'Bases y escoltas', F: 'Aleros y ala-pívots', C: 'Pívots' }
const pct = (share: number) => `${Math.round(share * 100)} %`
const dash = <span className="text-ink-faint" title="Sin dato">—</span>

export default function MyTeamPage() {
  const [params, setParams] = useSearchParams()
  const manifest = useQuery({ queryKey: ['talent-competitions'], queryFn: loadTalentCompetitions })
  const remembered = useMemo(recallTeam, [])
  const comp = params.get('c') ?? remembered?.comp ?? ''
  const teamId = params.get('e') ?? (params.has('c') ? '' : remembered?.team ?? '')
  const entry = manifest.data?.find(e => e.key === comp)
  const rows = useQuery({ queryKey: ['talent-rows', comp], queryFn: () => loadCompetitionRows(comp), enabled: Boolean(entry) })
  const all = useMemo(() => (rows.data && entry ? rows.data.rows.map(r => toSearchRow(entry, r)) : []), [rows.data, entry])
  const teams = useMemo(() => teamsOf(all), [all])
  const team = teams.find(t => t.team_id === teamId)
  const squad = useMemo(() => squadOf(all, comp, teamId), [all, comp, teamId])
  const balance = useMemo(() => positionBalance(squad.rotation), [squad])
  const gaps = useMemo(() => profileGaps(squad.rotation), [squad])
  const age = useMemo(() => ageMix(squad.rotation), [squad])
  const found = entry ? suggestions({ season: entry.season, balance, gaps }) : []

  useEffect(() => { if (team) rememberTeam({ comp, team: team.team_id }) }, [team, comp])

  const choose = (patch: { c?: string; e?: string }) => {
    const next = new URLSearchParams()
    const c = patch.c ?? comp
    if (c) next.set('c', c)
    const e = patch.e ?? (patch.c !== undefined ? '' : teamId)
    if (e) next.set('e', e)
    setParams(next, { replace: true })
  }

  if (manifest.isLoading) return <div className="flex justify-center p-12"><Spinner size="lg" label="Cargando competiciones" /></div>
  const unavailable = manifest.isError || (manifest.isSuccess && manifest.data.length === 0)
  const competitions = [...(manifest.data ?? [])].sort((a, b) => Number(b.season) - Number(a.season) || (a.competition_label ?? a.competition).localeCompare(b.competition_label ?? b.competition))
  return (
    <div className="mx-auto w-full max-w-5xl space-y-4 p-4 sm:p-6">
      <PageHeader title="Mi equipo" subtitle="Quién forma la rotación, dónde hay huecos y qué buscar para cubrirlos" />
      {unavailable ? (
        <EmptyState icon={Users} title="Aún no hay datos de jugadores publicados" description="Mi equipo aparece aquí en cuanto se publique el primer conjunto de datos." />
      ) : (
        <>
          <Card title="Tu equipo">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Competición">
                <Select value={comp} onChange={e => choose({ c: e.target.value })}
                  options={[{ value: '', label: 'Elige una competición' }, ...competitions.map(e => ({ value: e.key, label: `${e.season_label} · ${e.competition_label ?? e.competition}` }))]} />
              </Field>
              <Field label="Equipo">
                <Select value={team ? teamId : ''} disabled={!entry || rows.isLoading} onChange={e => choose({ e: e.target.value })}
                  options={[{ value: '', label: rows.isLoading ? 'Cargando equipos…' : 'Elige un equipo' }, ...teams.map(t => ({ value: t.team_id, label: t.team_name }))]} />
              </Field>
            </div>
          </Card>
          {!team && !rows.isLoading && !(entry && teamId) && <EmptyState icon={Users} title="Elige tu equipo" description="Elige la competición y el equipo; se recordará en este navegador." />}
          {entry && teamId && rows.isSuccess && !team && <EmptyState icon={Users} title="No encontramos ese equipo" description="El equipo de la dirección no está en esa competición y temporada." />}
          {team && (
            <>
              <Card title={`Rotación de ${team.team_name}`} padding="none">
                <div role="region" tabIndex={0} aria-label="Tabla de la rotación, desplazable" className="relative overflow-x-auto">
                  <table aria-label={`Rotación de ${team.team_name}`} className="w-full min-w-[28rem] border-collapse text-sm">
                    <thead>
                      <tr className="text-left text-xs text-ink-muted">
                        <th scope="col" className="p-2 font-medium">Jugador</th><th scope="col" className="p-2 font-medium">Posición</th><th scope="col" className="p-2 font-medium">Edad</th><th scope="col" className="p-2 font-medium">Min</th><th scope="col" className="p-2 font-medium">PJ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {squad.rotation.map(r => (
                        <tr key={r.person_id} className="border-t border-line/50">
                          <th scope="row" className="p-2 text-left font-normal"><Link to={`/jugador/${encodeURIComponent(r.person_id)}`} className="font-medium text-accent-text hover:underline">{r.full_name ?? r.name}</Link></th>
                          <td className="p-2 text-ink-muted">{r.position ?? r.position_group ?? dash}</td><td className="p-2 tabular-nums">{r.age ?? dash}</td>
                          <td className="p-2 tabular-nums">{Math.round(r.minutes / 60)}</td><td className="p-2 tabular-nums">{r.games}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {squad.rotation.length === 0 && <p className="p-4 text-sm text-ink-muted">Ningún jugador de este equipo tiene minutos suficientes todavía.</p>}
                {squad.bench.length > 0 && <p className="border-t border-line p-3 text-xs text-ink-muted">Fondo de plantilla (sin minutos suficientes): {squad.bench.map(r => r.full_name ?? r.name).join(', ')}.</p>}
              </Card>
              <Card title="Huecos de posición">
                {!balance.reliable ? (
                  <p className="text-sm text-ink-muted">Con {squad.rotation.length} {squad.rotation.length === 1 ? 'jugador' : 'jugadores'} de rotación todavía no se puede decir (hacen falta {MIN_ROTATION}).</p>
                ) : (
                  <ul aria-label="Huecos de posición" className="grid gap-2 sm:grid-cols-3">
                    {balance.groups.map(g => (
                      <li key={g.group} className="rounded-card border border-line p-3">
                        <p className="flex items-center justify-between gap-2 text-sm font-medium text-ink">{GROUP_NAME[g.group]}{g.hole && <Badge tone="bad">Hueco</Badge>}</p>
                        <p className="mt-1 text-xs text-ink-muted">{g.players} {g.players === 1 ? 'jugador' : 'jugadores'} · {pct(g.minutesShare)} de los minutos</p>
                      </li>
                    ))}
                  </ul>
                )}
                {balance.unknown.players > 0 && <p className="mt-2 text-xs text-ink-muted">{balance.unknown.players} {balance.unknown.players === 1 ? 'jugador' : 'jugadores'} sin posición: no cuentan en ningún grupo y un grupo solo es hueco si, aun sumándolos, no llega.</p>}
              </Card>
              <Card title="Huecos de perfil">
                {gaps.length === 0 ? <p className="text-sm text-ink-muted">Todavía no hay rotación suficiente para decir dónde es más flojo el equipo.</p> : (
                  <>
                    <p className="mb-2 text-xs text-ink-muted">Los tres ejes donde la rotación es más floja: el percentil de cada jugador en su competición, ponderado por minutos (50 es el término medio de la liga).</p>
                    <ul aria-label="Huecos de perfil" className="space-y-1.5">
                      {gaps.map(g => <li key={g.key} className="flex items-center justify-between gap-3 text-sm"><span className="text-ink">{g.label}</span><span className="font-semibold tabular-nums text-ink">{Math.round(g.mean)}</span></li>)}
                    </ul>
                  </>
                )}
              </Card>
              <Card title="Edad de la rotación">
                {age.young === null ? <p className="text-sm text-ink-muted">Sin edad conocida en la rotación.</p> : (
                  <p className="text-sm text-ink">{pct(age.young)} de los minutos son de menores de {AGE_YOUNG} y {pct(age.veteran ?? 0)} de {AGE_VETERAN} años o más{age.unknown > 0 ? ` (${pct(age.unknown)} de los minutos son de jugadores sin edad conocida)` : ''}.</p>
                )}
              </Card>
              {found.length > 0 && (
                <Card title="Para cubrirlos">
                  <p className="mb-2 text-xs text-ink-muted">Cada enlace abre el buscador con los filtros ya puestos (minutos suficientes y, en un eje, el percentil 75 o más); el percentil es el de cada jugador en su propia competición.</p>
                  <ul aria-label="Búsquedas sugeridas" className="space-y-1.5">
                    {found.map(s => <li key={s.key}><Link to={s.href} className="text-sm font-medium text-accent-text hover:underline">{s.label}</Link></li>)}
                  </ul>
                </Card>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
