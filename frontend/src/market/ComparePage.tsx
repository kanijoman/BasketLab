// The comparator of BasketLab Talent (B5, #881): two or three players side by side, in the address (`/comparar?j=feb:1,feb:2`). The rules are in `compare.ts`.
// Players of different leagues can be mixed: only the competitions that hold the chosen players are opened (a FEB person has his FEB ones and the FBCYL ones linked to him, `identities`), and all of them
// only while the staff types a name to add one. Each player is read in HIS competition and season: the page says that a percentile is never compared across competitions.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowDown, ArrowLeft, ArrowUp, Scale, X } from 'lucide-react'
import Checkbox from '@/components/ui/Checkbox'
import Card from '@/components/ui/Card'
import ExportButton from '@/components/ui/ExportButton'
import EmptyState from '@/components/ui/EmptyState'
import { Field, Input } from '@/components/ui/Field'
import Button, { IconButton } from '@/components/ui/Button'
import PageHeader from '@/components/ui/PageHeader'
import Spinner from '@/components/ui/Spinner'
import { rememberCompare } from './compareMemory'
import { axesToParam, compareCsv, compareLines, comparePlayers, DEFAULT_AXES, findPlayers, MAX_COMPARED, MIN_AXES, moveAxis, parseAxes, parseCompare, toggleAxis, toggleCompare } from './compare'
import { loadCompetitionRows, loadIdentities, loadTalentCompetitions } from './data'
import { RADAR_AXES, radarAxes } from './player'
import PlayerRadar from './PlayerRadar'
import { toSearchRow } from './search'

const dash = <span className="text-ink-faint" title="Sin dato">—</span>
const Shell = ({ children }: { children: React.ReactNode }) => <div className="mx-auto w-full max-w-5xl space-y-4 p-4 sm:p-6">{children}</div>
const Back = () => <Link to="/" className="inline-flex items-center gap-1 text-sm font-medium text-accent-text hover:underline"><ArrowLeft className="h-4 w-4" aria-hidden="true" />Volver al buscador</Link>

export default function ComparePage() {
  const [params, setParams] = useSearchParams()
  const ids = useMemo(() => parseCompare(params.get('j')), [params])
  const [typed, setTyped] = useState('')
  useEffect(() => { rememberCompare(ids) }, [ids])          // the navigation brings the comparison back (#1007)
  const manifest = useQuery({ queryKey: ['talent-competitions'], queryFn: loadTalentCompetitions })
  const identities = useQuery({ queryKey: ['talent-identities'], queryFn: loadIdentities })
  const searching = typed.trim().length >= 2
  const entries = useMemo(() => {
    const links = identities.data?.links ?? {}
    const wanted = new Set(ids.map(id => links[id] ?? id))
    const keys = new Set<string>()
    for (const id of wanted) for (const k of identities.data?.by_feb[id] ?? []) keys.add(k)
    const leagues = new Set([...wanted].map(id => (id.startsWith('fbcyl:') ? 'fbcyl' : 'feb')))
    return (manifest.data ?? []).filter(e => searching || leagues.has(e.league) || keys.has(e.key))
  }, [manifest.data, identities.data, ids, searching])
  const loaded = useQueries({ queries: entries.map(e => ({ queryKey: ['talent-rows', e.key], queryFn: () => loadCompetitionRows(e.key) })) })
  const rows = useMemo(() => loaded.flatMap((q, i) => (q.data ? q.data.rows.map(r => toSearchRow(entries[i], r)) : [])),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [loaded.map(q => q.dataUpdatedAt).join(), entries])
  const { players, missing } = useMemo(() => comparePlayers(rows, ids), [rows, ids])
  const axes = useMemo(() => parseAxes(params.get('ejes')), [params])          // the axes of the radar that are chosen (#1014)
  const lines = useMemo(() => compareLines(players, axes), [players, axes])
  const csv = useMemo(() => compareCsv(players, lines), [players, lines])
  const tableRef = useRef<HTMLTableElement>(null)
  const found = useMemo(() => (searching ? findPlayers(rows, typed, players.map(p => p.id)) : []), [rows, typed, searching, players])
  /** Change the address keeping what is not changed: the players (`j`) and the axes (`ejes`) are independent. */
  const setQuery = (patch: { j?: string[]; ejes?: string[] }) => {
    const next = new URLSearchParams(params)
    if (patch.j) { if (patch.j.length) next.set('j', patch.j.join(',')); else next.delete('j') }
    if (patch.ejes) { const value = axesToParam(patch.ejes); if (value) next.set('ejes', value); else next.delete('ejes') }
    setParams(next, { replace: true })
  }
  const setIds = (next: string[]) => setQuery({ j: next })
  const hidden = RADAR_AXES.filter(a => !axes.includes(a.key))

  if (manifest.isError || (manifest.isSuccess && manifest.data.length === 0)) {
    return <Shell><Back /><EmptyState icon={Scale} title="Aún no hay datos de jugadores publicados" description="El comparador aparece aquí en cuanto se publique el primer conjunto de datos." /></Shell>
  }
  const searchingNow = loaded.some(q => q.isLoading)
  const waiting = manifest.isLoading || identities.isLoading || (ids.length > 0 && searchingNow)
  const full = ids.length >= MAX_COMPARED
  return (
    <Shell>
      <Back />
      <PageHeader title="Comparador de jugadores" subtitle="De dos a tres jugadores, de cualquier liga: cada uno se lee en su competición y su última temporada" />
      <Card title="Jugadores">
        <div className="space-y-3">
          <ul aria-label="Jugadores elegidos" className="flex flex-wrap gap-2">
            {players.map(p => (
              <li key={p.id} className="flex items-center gap-1 rounded-card border border-line bg-surface px-2 py-1 text-sm">
                <Link to={`/jugador/${encodeURIComponent(p.id)}`} className="font-medium text-accent-text hover:underline">{p.name}</Link>
                <IconButton icon={X} label={`Quitar ${p.name}`} variant="ghost" size="sm" onClick={() => setIds(toggleCompare(ids, p.id))} />
              </li>
            ))}
          </ul>
          {missing.map(id => <p key={id} role="alert" className="text-sm text-bad">No encontramos a {id} en los datos publicados.</p>)}
          <Field label="Añadir jugador" hint={full ? `Ya hay ${MAX_COMPARED} jugadores: quita uno para añadir otro.` : 'Escribe al menos dos letras del nombre'}>
            <Input type="search" disabled={full} value={typed} onChange={e => setTyped(e.target.value)} placeholder="Nombre del jugador…" />
          </Field>
          {searching && !full && (
            <ul aria-label="Resultados" className="divide-y divide-line rounded-card border border-line">
              {searchingNow && <li className="p-2"><Spinner size="sm" label="Buscando" /></li>}
              {found.map(f => (
                <li key={f.id}>
                  <Button variant="ghost" className="!flex w-full flex-col !items-start !justify-start rounded-none px-3 py-2 text-left" onClick={() => { setIds(toggleCompare(ids, f.id)); setTyped('') }}>
                    <span className="font-medium text-ink">{f.name}</span><span className="text-xs text-ink-muted">{f.label}</span>
                  </Button>
                </li>
              ))}
              {!found.length && !searchingNow && <li className="p-2 text-sm text-ink-muted">Ningún jugador coincide.</li>}
            </ul>
          )}
        </div>
      </Card>
      {waiting && <div className="flex justify-center p-6"><Spinner size="lg" label="Cargando la comparación" /></div>}
      {!waiting && players.length < 2 && <EmptyState icon={Scale} title="Elige de dos a tres jugadores" description="Añádelos por su nombre o desde el buscador y la ficha." />}
      {!waiting && players.length >= 2 && (
        <>
          <p className="text-xs text-ink-muted">Cada percentil es el del jugador entre los de su competición y temporada: nunca se compara entre competiciones.</p>
          <Card title="Perfil">
            <div className="grid gap-4 sm:grid-cols-2">
              <PlayerRadar axes={radarAxes(players[0].row, axes)} name={players[0].name} others={players.slice(1).map(p => ({ name: p.name, axes: radarAxes(p.row, axes) }))} />
              <ul aria-label="Leyenda" className="space-y-1 self-center text-sm">
                {players.map((p, i) => (
                  <li key={p.id} className="flex items-center gap-2">
                    <span aria-hidden="true" className="inline-block h-3 w-3 rounded-sm" style={{ background: `var(--chart-${(i % 8) + 1})` }} />
                    <span className="font-medium text-ink">{p.name}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Card>
          <Card title="Ejes del radar" actions={axesToParam(axes) ? <Button variant="ghost" size="sm" onClick={() => setQuery({ ejes: DEFAULT_AXES })}>Restablecer los ejes</Button> : undefined}>
            <p className="mb-2 text-xs text-ink-muted">Elige qué ejes se dibujan y en qué orden (mínimo {MIN_AXES}); la tabla y la exportación siguen la misma elección.</p>
            <ul aria-label="Ejes del radar" className="grid gap-1 sm:grid-cols-2">
              {[...axes.map(k => RADAR_AXES.find(a => a.key === k)!), ...hidden].map(a => {
                const on = axes.includes(a.key)
                return (
                  <li key={a.key} className="flex items-center justify-between gap-2 rounded-card border border-line/60 px-2 py-1">
                    <Checkbox label={a.label} checked={on} disabled={on && axes.length <= MIN_AXES} onChange={() => setQuery({ ejes: toggleAxis(axes, a.key) })} className="min-w-0 flex-1 text-sm text-ink" />
                    {on && (
                      <span className="flex shrink-0">
                        <IconButton icon={ArrowUp} label={`Subir ${a.label}`} variant="ghost" size="sm" disabled={axes[0] === a.key} onClick={() => setQuery({ ejes: moveAxis(axes, a.key, -1) })} />
                        <IconButton icon={ArrowDown} label={`Bajar ${a.label}`} variant="ghost" size="sm" disabled={axes[axes.length - 1] === a.key} onClick={() => setQuery({ ejes: moveAxis(axes, a.key, 1) })} />
                      </span>
                    )}
                  </li>
                )
              })}
            </ul>
          </Card>
          <Card title="Comparación" padding="none" actions={<ExportButton filename={`comparacion-${players.map(p => p.id.replace(/\W+/g, '-')).join('_')}`} pdfTitle={`Comparación — ${players.map(p => p.name).join(' · ')}`} csvHeaders={csv.headers} csvData={csv.data} captureRef={tableRef} />}>
            {/* `relative`: the «(el mejor)» of the screen reader is absolute and, without it, would stretch the page (not the scroller) to the right on a phone */}
            <div role="region" tabIndex={0} aria-label="Tabla de comparación, desplazable" className="relative overflow-x-auto">
              <table ref={tableRef} aria-label="Comparación de jugadores" className="w-full min-w-[32rem] border-collapse text-sm">
                <thead>
                  <tr>
                    <th scope="col" className="p-2 text-left text-xs font-medium text-ink-muted"><span className="sr-only">Dato</span></th>
                    {players.map(p => <th key={p.id} scope="col" className="p-2 text-left font-medium text-ink">{p.name}</th>)}
                    {players.length === 2 && <th scope="col" className="p-2 text-left font-medium text-ink-muted">Diferencia</th>}
                  </tr>
                </thead>
                <tbody>
                  {lines.map((l, i) => (
                    <tr key={l.group + l.key} className={i > 0 && lines[i - 1].group !== l.group ? 'border-t-2 border-line' : 'border-t border-line/50'}>
                      <th scope="row" className="p-2 text-left font-normal text-ink-muted">{l.label}</th>
                      {l.cells.map((c, k) => (
                        <td key={players[k].id} className={`p-2 tabular-nums ${c.best ? 'font-semibold text-ok' : 'text-ink'}`}>
                          {c.text ?? dash}{c.best && <span className="sr-only"> (el mejor)</span>}
                        </td>
                      ))}
                      {players.length === 2 && <td className="p-2 tabular-nums text-ink-muted">{l.diff ?? dash}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </Shell>
  )
}
