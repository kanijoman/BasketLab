// The fit of the player of the profile with the team of «Mi equipo» (C2, #883): complements, collides, whom he would replace and the holes of the team with and without him. The team is the one
// remembered in this browser (`myTeamMemory.ts`); its rows are the ones of the search (same key and cache). The rules are in `fit.ts`; the percentiles are each player's in HIS competition.
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import Badge from '@/components/ui/Badge'
import Card from '@/components/ui/Card'
import Spinner from '@/components/ui/Spinner'
import { loadCompetitionRows, loadTalentCompetitions } from './data'
import { fitIn, SUBSTITUTE_SIMILARITY, type Fit } from './fit'
import { COVER_PCT, MIN_ROTATION, AXES, squadOf, teamsOf } from './myTeam'
import { recallTeam } from './myTeamMemory'
import { toSearchRow, type SearchRow } from './search'

const REASON = {
  'no-profile': 'Sin encaje: este jugador está sin perfil en esta competición.',
  'few-minutes': 'Sin encaje: este jugador no tiene minutos suficientes en esta competición y su perfil sería orientativo.',
  'small-rotation': `Todavía no se puede decir: la rotación del equipo tiene menos de ${MIN_ROTATION} jugadores.`,
  'in-team': 'Este jugador ya está en este equipo.',
} as const
const names = (keys: string[]) => keys.map(k => AXES.find(a => a.key === k)?.label.toLowerCase() ?? k).join(', ')
const nameOf = (r: SearchRow) => r.full_name ?? r.name

function Verdict({ fit, team }: { fit: Fit; team: string }) {
  if (fit.verdict === 'complements') return <p className="text-sm text-ink"><Badge tone="ok">Complementa</Badge> A {team} le falta {names(fit.fills.map(a => a.key))}, y él destaca ahí (percentil {COVER_PCT} o más).</p>
  if (fit.verdict === 'collides') return (
    <p className="text-sm text-ink"><Badge tone="warn">Coincide</Badge> Solo destaca en {names(fit.collides.map(c => c.axis.key))}, y {team} ya lo tiene cubierto
      ({fit.collides.map((c, i) => <span key={c.axis.key}>{i > 0 && ', '}<Link to={`/jugador/${encodeURIComponent(c.by.person_id)}`} className="font-medium text-accent-text hover:underline">{nameOf(c.by)}</Link></span>)}).</p>
  )
  return <p className="text-sm text-ink"><Badge tone="neutral">Neutro</Badge> No destaca en ningún eje (percentil {COVER_PCT} o más): ni cubre un hueco de {team} ni coincide con nadie.</p>
}

export function FitDetail({ fit, team }: { fit: Fit; team: string }) {
  if (fit.reason) return <p className="text-sm text-ink-muted">{REASON[fit.reason]}</p>
  const none = 'ninguno'
  return (
    <div className="space-y-3">
      <Verdict fit={fit} team={team} />
      <p className="text-sm text-ink-muted">
        {fit.substitute
          ? <>Se parece a <Link to={`/jugador/${encodeURIComponent(fit.substitute.row.person_id)}`} className="font-medium text-accent-text hover:underline">{nameOf(fit.substitute.row)}</Link> ({Math.round(fit.substitute.similarity)} %): ocuparía su lugar en la rotación.</>
          : `Nadie de la rotación se le parece lo bastante (${SUBSTITUTE_SIMILARITY} % o más): se sumaría a ella.`}
      </p>
      <ul aria-label="Huecos del equipo" className="space-y-1 text-sm">
        <li><span className="text-ink-muted">Huecos ahora:</span> <span className="font-medium text-ink">{fit.holesBefore.length ? names(fit.holesBefore) : none}</span></li>
        <li><span className="text-ink-muted">Huecos con él:</span> <span className="font-medium text-ink">{fit.holesAfter.length ? names(fit.holesAfter) : none}</span></li>
      </ul>
      {fit.opens.length > 0 && <p role="status" className="text-xs text-warn">Ojo: al ocupar el lugar de {fit.replaced ? nameOf(fit.replaced) : 'otro'} se abre un hueco en {names(fit.opens)}.</p>}
    </div>
  )
}

export default function TeamFit({ row }: { row: SearchRow }) {
  const chosen = useMemo(recallTeam, [])
  const manifest = useQuery({ queryKey: ['talent-competitions'], queryFn: loadTalentCompetitions })
  const entry = chosen ? manifest.data?.find(e => e.key === chosen.comp) : undefined
  const rows = useQuery({ queryKey: ['talent-rows', chosen?.comp], queryFn: () => loadCompetitionRows(chosen!.comp), enabled: Boolean(entry) })
  const all = useMemo(() => (rows.data && entry ? rows.data.rows.map(r => toSearchRow(entry, r)) : []), [rows.data, entry])
  const team = useMemo(() => teamsOf(all).find(t => t.team_id === chosen?.team), [all, chosen])
  const fit = useMemo(() => (chosen && team ? fitIn(squadOf(all, chosen.comp, chosen.team).rotation, row) : null), [all, chosen, team, row])
  const toMyTeam = <Link to="/mi-equipo" className="font-medium text-accent-text hover:underline">Mi equipo</Link>
  return (
    <Card id="encaje" title="Encaje con tu equipo">
      {!chosen && <p className="text-sm text-ink-muted">Elige tu equipo en {toMyTeam} para ver cómo encajaría este jugador.</p>}
      {chosen && (manifest.isLoading || rows.isLoading) && <Spinner size="sm" label="Calculando el encaje" />}
      {chosen && !manifest.isLoading && !rows.isLoading && !team && <p className="text-sm text-ink-muted">El equipo que elegiste ya no está en los datos publicados: elígelo de nuevo en {toMyTeam}.</p>}
      {chosen && team && fit && (
        <>
          <p className="mb-2 text-xs text-ink-muted">Equipo: <span className="font-medium text-ink">{team.team_name}</span> ({entry?.season_label} · {entry?.competition_label ?? entry?.competition}) · {toMyTeam}</p>
          <FitDetail fit={fit} team={team.team_name} />
          <p className="mt-3 text-xs text-ink-muted">
            Los percentiles son los de cada jugador en su competición, sin traducir de una a otra{row.comp_key !== chosen.comp ? ': este jugador compite en otra, así que el encaje es orientativo' : ''}.
            El perfil que se juzga es el de la temporada elegida arriba. Es información para el staff, no una orden de fichar.
          </p>
        </>
      )}
    </Card>
  )
}
