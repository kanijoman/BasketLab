/** The Partidos tab (issue #224): the packages published for the next matches, the import of a file and the package that is loaded. */
import type { EngineApi } from '../engine/client'
import type { ReactNode } from 'react'
import type { Fetcher } from '../package/remote'
import type { PackageStore } from '../package/storage'
import type { PackageSummary } from '../package/summary'
import PackagePanel from './PackagePanel'
import RemotePackages from './RemotePackages'

interface Props {
  engine: EngineApi
  store: PackageStore
  loaded: PackageSummary | null
  onLoaded: (summary: PackageSummary) => void
  onRemoved: () => void
  fetcher?: Fetcher
  /** What an invitation link said when it opened the app (issue #410). */
  notice?: string | null
  /** The matches to open or review (demos, finished, recorded), under the packages (issue #476). */
  library?: ReactNode
}

export default function PackagesTab({ engine, store, loaded, onLoaded, onRemoved, fetcher, notice, library }: Props) {
  return (
    <>
      {notice && <p role="status" className="status">{notice}</p>}
      <RemotePackages engine={engine} store={store} onLoaded={onLoaded} fetcher={fetcher} loaded={loaded} />
      <PackagePanel engine={engine} store={store} loaded={loaded} onLoaded={onLoaded} onRemoved={onRemoved} />
      {library}
    </>
  )
}
