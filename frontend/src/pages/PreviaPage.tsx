/**
 * Previa del partido (issue #849): choose a team (our point of view), see ITS calendar of matches to play, choose the match to analyse and read the forecast, the scenarios, the objectives of the
 * match and the matchup for that rival and that court. Everything is computed in the browser from the published games (`forecast/`); the team and the match are in the address so that a
 * preview can be shared and reloaded, and the team is remembered per competition.
 */
import { useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CalendarX2, Crosshair } from 'lucide-react'
import { leverEvidence, leverTitle, paceLines, pct, SCENARIO_TEXT } from '@/forecast/copy'
import { nextFixture, teamFixtures } from '@/forecast/fixtures'
import { buildPreview } from '@/forecast/preview'
import { loadPrefs, savePrefs } from '@/forecast/storage'
import { useForecast } from '@/forecast/useForecast'
import { useCollection } from '@/context/CollectionContext'
import EmptyState from '@/components/ui/EmptyState'
import ExportButton from '@/components/ui/ExportButton'
import PageHeader from '@/components/ui/PageHeader'
import PageTransition from '@/components/ui/PageTransition'
import Spinner from '@/components/ui/Spinner'
import { Field, Select } from '@/components/ui/Field'
import Forecast from './previa/Forecast'
import HowItWorks from './previa/HowItWorks'
import MatchupTable from './previa/MatchupTable'
import ObjectivesList from './previa/ObjectivesList'
import ScenariosChart from './previa/ScenariosChart'
import TeamFixtures from './previa/TeamFixtures'
import { courtText } from './previa/format'

export default function PreviaPage() {
  const { collection } = useCollection()
  const name = collection?.name
  const { model, calendar, teams, isLoading, error } = useForecast(name)
  const [params, setParams] = useSearchParams()
  const captureRef = useRef<HTMLDivElement>(null)

  const requested = params.get('equipo') ?? (name ? loadPrefs(name).team : undefined)
  const team = requested && teams.some(t => t.id === requested) ? requested : null
  const fixtures = useMemo(() => (model && calendar && team ? teamFixtures(model.games, calendar, team) : []), [model, calendar, team])
  const fixture = fixtures.find(f => f.code === params.get('partido')) ?? nextFixture(fixtures, Date.now())
  const preview = useMemo(() => (model && team && fixture ? buildPreview(model, team, fixture.rival, fixture.court) : null), [model, team, fixture])
  const ownName = teams.find(t => t.id === team)?.name ?? ''

  const chooseTeam = (id: string) => {
    if (name) savePrefs(name, { team: id || undefined })
    setParams(id ? { equipo: id } : {})
  }

  const header = <PageHeader title="Previa del partido" subtitle={collection?.label} icon={Crosshair} />
  if (isLoading || (!model && !error)) return <PageTransition><div className="space-y-4">{header}<Spinner /></div></PageTransition>
  if (error) return <PageTransition><div className="space-y-4">{header}<p role="alert" className="rounded-lg border border-bad/30 bg-bad/10 p-3 text-sm text-bad">{error instanceof Error ? error.message : String(error)}</p></div></PageTransition>
  if (!calendar) return <PageTransition><div className="space-y-4">{header}<EmptyState icon={CalendarX2} title="Esta competición todavía no tiene el calendario publicado." description="La previa necesita los partidos que quedan por jugar." /></div></PageTransition>

  const detail = preview?.detail ?? null
  const csv = detail ? [
    ...[...detail.levers.attack, ...detail.levers.defence].map(l => ({ tipo: 'Objetivo', texto: leverTitle(l), victorias: pct(l.pWin, 0), temporada: leverEvidence(l) })),
    { tipo: 'Ritmo (informativo)', texto: paceLines(detail.levers.pace).summary, victorias: '', temporada: paceLines(detail.levers.pace).record },
    ...detail.scenarios.map(b => ({ tipo: 'Escenario', texto: SCENARIO_TEXT[b.id].title, victorias: pct(b.p, 0), temporada: '' })),
  ] : []

  return (
    <PageTransition>
      <div className="space-y-5">
        {header}
        <div className="card flex flex-wrap items-end gap-3 p-4">
          <Field label="Equipo">
            <Select aria-label="Equipo" value={team ?? ''} onChange={e => chooseTeam(e.target.value)}>
              <option value="">Elige tu equipo</option>
              {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </Select>
          </Field>
        </div>

        {!team && <p className="text-sm text-ink-muted">Elige tu equipo para ver sus próximos partidos.</p>}
        {team && !fixtures.length && <EmptyState icon={CalendarX2} title="No quedan partidos pendientes de este equipo." />}
        {team && fixtures.length > 0 && (
          <section aria-label="Calendario" className="space-y-2">
            <h2 className="text-lg font-semibold text-ink">Próximos partidos de {ownName}</h2>
            <p className="text-sm text-ink-muted">Elige el partido que quieres analizar; el análisis aparece debajo.</p>
            <TeamFixtures fixtures={fixtures} selected={fixture?.code ?? null} onSelect={code => { setParams({ equipo: team, partido: code }); captureRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }) }} />
          </section>
        )}

        {preview && fixture && (
          <div ref={captureRef} className="space-y-6 rounded-lg bg-canvas">
            <div className="flex flex-wrap items-center gap-3">
              <p data-testid="preview-title" className="text-xl font-bold text-ink">{ownName} – {fixture.rivalName} · {courtText(fixture.court)}</p>
              <ExportButton className="ml-auto" filename={`previa-${ownName}-${fixture.rivalName}`} captureRef={captureRef} pdfTitle={`Previa: ${ownName} – ${fixture.rivalName}`}
                csvData={csv} csvHeaders={[{ key: 'tipo', label: 'Tipo' }, { key: 'texto', label: 'Qué' }, { key: 'victorias', label: 'Victorias' }, { key: 'temporada', label: 'Esta temporada' }]} />
            </div>
            <Forecast preview={preview} ownName={ownName} />
            {detail && <ScenariosChart detail={detail} />}
            {detail && <ObjectivesList detail={detail} headline={preview.headline.p} />}
            {detail && <MatchupTable rows={detail.matchup} />}
            <HowItWorks poolSize={detail?.poolSize ?? null} />
          </div>
        )}
      </div>
    </PageTransition>
  )
}
