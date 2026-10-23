/** The Partidos tab (issue #224): the kind of match is chosen with a selector (live, demos, finished) and only the list of that kind is shown. */
import type { EngineApi } from '../engine/client'
import type { ReactNode } from 'react'
import type { Fetcher } from '../package/remote'
import type { PackageStore } from '../package/storage'
import type { PackageSummary } from '../package/summary'
import PackagePanel from './PackagePanel'
import RemotePackages from './RemotePackages'

export type MatchKind = 'live' | 'demo' | 'finished'
const KINDS: { id: MatchKind; label: string }[] = [
  { id: 'live', label: 'En directo' },
  { id: 'demo', label: 'Demos' },
  { id: 'finished', label: 'Finalizados' },
]

interface Props {
  engine: EngineApi
  store: PackageStore
  loaded: PackageSummary | null
  onLoaded: (summary: PackageSummary) => void
  onRemoved: () => void
  fetcher?: Fetcher
  /** What an invitation link said when it opened the app (issue #410). */
  notice?: string | null
  /** The kind of match listed; it is kept by the app so that it survives a change of tab. */
  kind?: MatchKind
  onKind?: (kind: MatchKind) => void
  /** The loaded match is the one on the Partido tab (issue #509); `onOpenLoaded` goes back to it when a demo is open. */
  viewing?: boolean
  onOpenLoaded?: () => void
  /** The demos, and the finished matches and recordings kept on the device (issue #476). */
  demos?: ReactNode
  finished?: ReactNode
}

export default function PackagesTab({ engine, store, loaded, onLoaded, onRemoved, fetcher, notice, kind = 'live', onKind, demos, finished, viewing, onOpenLoaded }: Props) {
  return (
    <>
      {notice && <p role="status" className="status">{notice}</p>}
      {onKind && (
        <label className="kind-select">
          Tipo de partido
          <select value={kind} onChange={e => onKind(e.target.value as MatchKind)}>
            {KINDS.map(k => <option key={k.id} value={k.id}>{k.label}</option>)}
          </select>
        </label>
      )}
      {kind === 'live' && (
        <>
          <RemotePackages engine={engine} store={store} onLoaded={onLoaded} fetcher={fetcher} loaded={loaded} viewing={viewing} onOpenLoaded={onOpenLoaded} />
          <PackagePanel engine={engine} store={store} loaded={loaded} onLoaded={onLoaded} onRemoved={onRemoved} viewing={viewing} onOpenLoaded={onOpenLoaded} />
        </>
      )}
      {kind === 'demo' && demos}
      {kind === 'finished' && (finished ?? <p className="detail">Todavía no hay partidos finalizados.</p>)}
    </>
  )
}
