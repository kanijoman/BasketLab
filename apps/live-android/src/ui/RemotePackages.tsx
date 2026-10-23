/** Packages published by BasketLab for the next matches: list, download, decrypt and install (issues #175, #410). */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { EngineApi } from '../engine/client'
import { decryptPackage, decryptScoped, isScoped, type Wrap } from '../package/crypto'
import { installPackage } from '../package/install'
import HelpHint from './HelpHint'
import { failureText, loadPassphrase, savePassphrase } from '../package/passphrase'
import PasswordField from './PasswordField'
import { fetchIndex, fetchPackageText, fetchRoundText, parseRoundBundle, pickPackage, type Fetcher, type PackageIndexEntry, type RoundBundle, type RoundIndexEntry, type RoundMatch } from '../package/remote'
import { RIGHTS_EVENT, addRight, loadRights, parseInvite, scopeKeys } from '../package/rights'
import RoundPackages from './RoundPackages'
import type { PackageStore } from '../package/storage'
import type { PackageSummary } from '../package/summary'

interface Props {
  engine: EngineApi
  store: PackageStore
  onLoaded: (summary: PackageSummary) => void
  fetcher?: Fetcher
  /** The package that is loaded now (the app knows it: it survives a restart). Without it the component remembers what it downloaded. */
  loaded?: PackageSummary | null
  /** The loaded match is the one on the Partido tab (false while a demo is open); `onOpenLoaded` goes back to it (issue #509). */
  viewing?: boolean
  onOpenLoaded?: () => void
}

function when(entry: PackageIndexEntry): string {
  const start = entry.match.start
  const d = start ? new Date(start) : null
  if (!d || Number.isNaN(d.getTime())) return 'fecha por confirmar'
  return `${d.toLocaleDateString('es-ES')} ${d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`
}

export default function RemotePackages({ engine, store, onLoaded, fetcher, loaded, viewing, onOpenLoaded }: Props) {
  const [entries, setEntries] = useState<PackageIndexEntry[] | null>(null)
  const [rounds, setRounds] = useState<RoundIndexEntry[]>([])
  const [openKey, setOpenKey] = useState<string | null>(null)
  const [rights, setRights] = useState(() => loadRights())
  const [invite, setInvite] = useState('')
  const bundles = useRef(new Map<string, RoundBundle>())   // a bundle is downloaded and decrypted once, however many of its matches are used
  const [pass, setPass] = useState(loadPassphrase)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // what was just downloaded: the message and which match and side it was (issue #342)
  const [got, setGot] = useState<{ code: string; ownId: string; text: string } | null>(null)

  const keys = useMemo(() => scopeKeys({ open_key: openKey }, rights), [openKey, rights])
  /** Sealed by scope (issue #410): the right of the device decides. Without `wraps` it is the old password. */
  const canOpen = useCallback((wraps?: Wrap[]) => (wraps ? wraps.some(w => keys.some(k => k.scope === w.scope)) : !!pass), [keys, pass])
  const open = (text: string, wraps?: Wrap[]) => (isScoped(text) ? decryptScoped(text, wraps ?? [], keys) : decryptPackage(text, pass))

  useEffect(() => {
    const reload = () => setRights(loadRights())
    window.addEventListener(RIGHTS_EVENT, reload)
    return () => window.removeEventListener(RIGHTS_EVENT, reload)
  }, [])

  /** Is this match, as seen from this team, the package that is loaded? The app says it (`loaded`); alone, the last download counts. */
  const isLoaded = useCallback((code: string, ownId: string) =>
    loaded !== undefined ? loaded?.match?.code === code && loaded.teamId === ownId : got?.code === code && got.ownId === ownId, [loaded, got])

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const index = await fetchIndex(fetcher)
      setEntries(index.packages)
      setRounds(index.rounds)
      setOpenKey(index.open_key ?? null)
    } catch (e) {
      setEntries(null)
      setRounds([])
      setOpenKey(null)
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [fetcher])

  useEffect(() => { void refresh() }, [refresh])

  async function download(entry: PackageIndexEntry) {
    setBusy(entry.file)
    setError(null)
    setGot(null)
    try {
      const text = await fetchPackageText(entry, fetcher)
      const plaintext = await open(text, entry.wraps)
      const summary = await installPackage(engine, store, plaintext)
      if (!isScoped(text)) savePassphrase(pass) // only once it is known to be right
      setGot({ code: entry.match.code, ownId: entry.team_id, text: `${summary.team} contra ${summary.rival}` })
      onLoaded(summary)
    } catch (e) {
      setError(failureText(e, pass))
    } finally {
      setBusy(null)
    }
  }

  async function downloadRoundMatch(round: RoundIndexEntry, match: RoundMatch, ownId: string) {
    setBusy(`${round.file}#${match.code}#${ownId}`)
    setError(null)
    setGot(null)
    try {
      let bundle = bundles.current.get(round.file)
      let sealed = false
      if (!bundle) {
        const text = await fetchRoundText(round, fetcher)
        sealed = isScoped(text)
        bundle = parseRoundBundle(await open(text, round.wraps))
        bundles.current.set(round.file, bundle)
      }
      const text = pickPackage(bundle, match.code, ownId)
      if (!text) throw new Error('El partido ya no está en la jornada publicada. Actualiza la lista.')
      const summary = await installPackage(engine, store, text)
      if (!sealed) savePassphrase(pass)
      setGot({ code: match.code, ownId, text: `${summary.team} contra ${summary.rival}` })
      onLoaded(summary)
    } catch (e) {
      setError(failureText(e, pass))
    } finally {
      setBusy(null)
    }
  }

  function useInvitation() {
    try {
      addRight(parseInvite(invite))
      setRights(loadRights())
      setInvite('')
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const anything = (entries !== null && entries.length > 0) || rounds.length > 0
  const withPassword = (entries ?? []).some(e => !e.wraps) || rounds.some(r => !r.wraps)
  const sealed = (entries ?? []).some(e => e.wraps) || rounds.some(r => r.wraps)
  const hasOpen = keys.some(k => k.scope === 'abierto')

  return (
    <section className="panel">
      <h2>Próximos partidos</h2>
      {entries?.length === 0 && rounds.length === 0 && <p className="detail">No hay partidos publicados todavía.</p>}
      {anything && (
        <>
          {withPassword && (
            <>
              <PasswordField className="remote-packages-pass" label="Contraseña de los paquetes publicados" value={pass} onChange={setPass} />
              <HelpHint label="Ayuda sobre los paquetes publicados">
                Los paquetes publicados van cifrados. Es la contraseña que fijó quien los genera (BasketLab → Preparación live o el
                secreto PACKAGE_PASSWORD). Se escribe una vez y queda guardada en este dispositivo.
              </HelpHint>
            </>
          )}
          {sealed && (
            <>
              {hasOpen
                ? <p className="detail">Acceso abierto: no necesitas contraseña.</p>
                : <p className="detail">{rights.length === 0 ? 'Sin acceso: pega la invitación que te enviaron.' : `Tu acceso: ${rights.map(r => r.scope).join(', ')}.`}</p>}
              {!hasOpen && (
                <div className="invite-field">
                  <label className="remote-packages-pass">
                    Invitación (enlace o clave)
                    <input value={invite} onChange={e => setInvite(e.target.value)} autoComplete="off" autoCapitalize="off" autoCorrect="off" spellCheck={false} />
                  </label>
                  <button type="button" className="secondary" disabled={!invite.trim()} onClick={useInvitation}>Usar invitación</button>
                </div>
              )}
            </>
          )}
          <ul className="remote-packages">
            {(entries ?? []).map(entry => (
              <li key={entry.file}>
                <span>
                  <strong>{entry.rival}</strong>
                  <span className="detail"> · {when(entry)}{entry.match.round ? ` · jornada ${entry.match.round}` : ''}</span>
                </span>
                <button disabled={isLoaded(entry.match.code, entry.team_id) || !canOpen(entry.wraps) || busy !== null} onClick={() => void download(entry)}>
                  {isLoaded(entry.match.code, entry.team_id) ? 'Ya disponible' : busy === entry.file ? 'Descargando…' : 'Descargar'}
                </button>
              </li>
            ))}
          </ul>
          <RoundPackages rounds={rounds} canOpen={round => canOpen(round.wraps)} busy={busy}
            onDownload={(round, match, ownId) => void downloadRoundMatch(round, match, ownId)} isLoaded={isLoaded}
            viewing={viewing} onOpenLoaded={onOpenLoaded} />
        </>
      )}
      <button className="secondary" disabled={busy !== null} onClick={() => void refresh()}>Actualizar lista</button>
      {got && !error && <p role="status" className="status">Descargado: {got.text}. Ya puedes seguirlo desde la pestaña Partido.</p>}
      {error && <p role="alert" className="status error">{error}</p>}
    </section>
  )
}
