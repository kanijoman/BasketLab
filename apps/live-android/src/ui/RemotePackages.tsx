/** Packages published by BasketLab for the next matches: list, download, decrypt and install (issue #175). */
import { useCallback, useEffect, useState } from 'react'
import type { EngineApi } from '../engine/client'
import { decryptEnvelope } from '../package/crypto'
import { installPackage } from '../package/install'
import { loadPassphrase, savePassphrase } from '../package/passphrase'
import { fetchIndex, fetchPackageText, type Fetcher, type PackageIndexEntry } from '../package/remote'
import type { PackageStore } from '../package/storage'
import type { PackageSummary } from '../package/summary'

interface Props {
  engine: EngineApi
  store: PackageStore
  onLoaded: (summary: PackageSummary) => void
  fetcher?: Fetcher
}

function when(entry: PackageIndexEntry): string {
  const start = entry.match.start
  const d = start ? new Date(start) : null
  if (!d || Number.isNaN(d.getTime())) return 'fecha por confirmar'
  return `${d.toLocaleDateString('es-ES')} ${d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`
}

export default function RemotePackages({ engine, store, onLoaded, fetcher }: Props) {
  const [entries, setEntries] = useState<PackageIndexEntry[] | null>(null)
  const [pass, setPass] = useState(loadPassphrase)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setEntries((await fetchIndex(fetcher)).packages)
    } catch (e) {
      setEntries(null)
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [fetcher])

  useEffect(() => { void refresh() }, [refresh])

  async function download(entry: PackageIndexEntry) {
    setBusy(entry.file)
    setError(null)
    try {
      const plaintext = await decryptEnvelope(await fetchPackageText(entry, fetcher), pass)
      const summary = await installPackage(engine, store, plaintext)
      savePassphrase(pass) // only once it is known to be right
      onLoaded(summary)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="panel">
      <h2>Próximos partidos</h2>
      {entries?.length === 0 && <p className="detail">No hay paquetes publicados todavía.</p>}
      {entries && entries.length > 0 && (
        <>
          <label>
            Contraseña de los paquetes publicados
            <input type="password" value={pass} onChange={e => setPass(e.target.value)} autoComplete="off" />
          </label>
          <ul className="remote-packages">
            {entries.map(entry => (
              <li key={entry.file}>
                <span>
                  <strong>{entry.rival}</strong>
                  <span className="detail"> · {when(entry)}{entry.match.round ? ` · jornada ${entry.match.round}` : ''}</span>
                </span>
                <button disabled={!pass || busy !== null} onClick={() => void download(entry)}>
                  {busy === entry.file ? 'Descargando…' : 'Descargar'}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <button className="secondary" disabled={busy !== null} onClick={() => void refresh()}>Actualizar lista</button>
      {error && <p role="alert" className="status error">{error}</p>}
    </section>
  )
}
