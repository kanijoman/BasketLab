/** About the app: version, update check and diagnostics to attach to an issue (issues #226 and #227). */
import { useState } from 'react'
import markUrl from '@design/brand/live-mark.svg'
import { useTheme, type ThemePreference } from './useTheme'
import type { AppVersion } from '../about/appInfo'
import type { LatestInfo, UpdateResult } from '../about/update'

export const REPO_URL = 'https://github.com/kanijoman/BasketLab'
export const RELEASES_URL = `${REPO_URL}/releases`

interface DiagnosticsInput {
  version: AppVersion | null
  userAgent: string
  packageId: string | null
  schemaVersion: number | null
  feed: string | null
  engineVersion?: string | null
  /** Latest events of the session, newest first (issue #309). */
  sessionLog?: string[]
}

/** Plain text with what is needed to report a problem; nothing secret (no package contents, no passphrase). */
export function buildDiagnostics(d: DiagnosticsInput): string {
  const v = d.version
  return [
    v ? `BasketLab Live ${v.name}${v.build !== null ? ` (build ${v.build})` : ''}` : 'BasketLab Live (versión desconocida)',
    `Compilada: ${v?.builtAt ?? 'desconocido'}`,
    `Motor: ${d.engineVersion ?? 'desconocido'}`,
    `Dispositivo: ${d.userAgent}`,
    d.packageId ? `Paquete: ${d.packageId} (esquema de paquete ${d.schemaVersion ?? '?'})` : 'Paquete: sin paquete',
    `Conexión: ${d.feed ?? 'sin conexión'}`,
    ...(d.sessionLog && d.sessionLog.length ? ['Registro reciente:', ...d.sessionLog.map(line => `- ${line}`)] : []),
  ].join('\n')
}

/** Discreet notice at the top: a newer version is published. The caller hides it during a match. */
export function UpdateBanner({ latest, onOpen }: { latest: LatestInfo; onOpen: (url: string) => void }) {
  return (
    <div className="update-banner" role="status" aria-label="Actualización disponible">
      <span>Hay una versión nueva: {latest.version}</span>
      <button type="button" onClick={() => onOpen(latest.apk)}>Actualizar</button>
    </div>
  )
}

/** One discreet line with the versions, always at hand in the match screen. */
export function VersionFooter({ version, engineVersion }: { version: AppVersion | null; engineVersion: string | null }) {
  const app = version && version.name !== 'dev' ? version.name : 'desarrollo'
  return <p className="version-footer">BasketLab Live {app}{engineVersion ? ` · motor ${engineVersion}` : ''}</p>
}

interface Props {
  /** Latest events of the session, newest first: what happened to the match on this device (issue #309). */
  sessionLog?: string[]
  /** Experimental features the staff can switch off on this device (issue #257). */
  experimental?: { winProb: boolean; onWinProb: (on: boolean) => void }
  engineVersion?: string | null
  schemaVersion?: number | null
  version: AppVersion | null
  update: UpdateResult | null
  checking: boolean
  onCheck: () => void
  onOpen: (url: string) => void
  diagnostics: string
}

function UpdateStatus({ update, onOpen }: { update: UpdateResult | null; onOpen: (url: string) => void }) {
  if (!update || update.status === 'unsupported') return null
  if (update.status === 'unknown') return <p className="detail">No se pudo comprobar la última versión (¿sin conexión?).</p>
  if (update.status === 'up_to_date') return <p className="detail">Tienes la última versión.</p>
  const { latest } = update
  return (
    <div className="update-available">
      <p><strong>Hay una versión nueva: {latest.version}</strong></p>
      {latest.notes && <p className="detail">{latest.notes}</p>}
      <p className="detail">Android pedirá confirmación para instalarla (y, si hace falta, permitir apps desconocidas).</p>
      <button type="button" onClick={() => onOpen(latest.apk)}>Descargar e instalar</button>
    </div>
  )
}

const APPEARANCE: { value: ThemePreference; label: string }[] = [
  { value: 'system', label: 'Sistema' }, { value: 'light', label: 'Claro' }, { value: 'dark', label: 'Oscuro' },
]

export default function AboutPanel({ sessionLog, experimental, engineVersion, schemaVersion, version, update, checking, onCheck, onOpen, diagnostics }: Props) {
  const { preference, setPreference } = useTheme()
  const [note, setNote] = useState<{ text: string; error: boolean } | null>(null)
  const dev = !version || version.name === 'dev'

  const copy = async () => {
    try {
      if (!navigator.clipboard) throw new Error('clipboard unavailable')
      await navigator.clipboard.writeText(diagnostics)
      setNote({ text: 'Copiado', error: false })
    } catch {
      setNote({ text: 'No se pudo copiar el diagnóstico', error: true })
    }
  }

  return (
    <section className="panel about-panel" aria-label="Acerca de">
      <img src={markUrl} alt="" width={72} height={72} aria-hidden="true" className="about-logo" />
      <h2>Acerca de</h2>
      <p>
        {dev ? 'BasketLab Live · versión de desarrollo' : `BasketLab Live ${version!.name}${version!.build !== null ? ` · build ${version!.build}` : ''}`}
      </p>
      {version?.builtAt && <p className="detail">Compilada el {version.builtAt.slice(0, 10)}</p>}
      {(engineVersion || schemaVersion) && (
        <p className="detail">
          {[engineVersion && `Motor ${engineVersion}`, schemaVersion && `esquema de paquete ${schemaVersion}`].filter(Boolean).join(' · ')}
        </p>
      )}
      <UpdateStatus update={update} onOpen={onOpen} />
      <div className="about-actions">
        {update?.status !== 'unsupported' && version?.native && (
          <button type="button" className="secondary" disabled={checking} onClick={onCheck}>
            {checking ? 'Buscando…' : 'Buscar actualización'}
          </button>
        )}
        <button type="button" className="secondary" onClick={() => void copy()}>Copiar diagnóstico</button>
        <button type="button" className="secondary" onClick={() => onOpen(REPO_URL)}>Repositorio</button>
        <button type="button" className="secondary" onClick={() => onOpen(RELEASES_URL)}>Notas de la versión</button>
      </div>
      <fieldset className="appearance" role="radiogroup" aria-label="Apariencia">
        <legend>Apariencia</legend>
        {APPEARANCE.map(option => (
          <label key={option.value}>
            <input type="radio" name="appearance" checked={preference === option.value} onChange={() => setPreference(option.value)} />
            {' '}{option.label}
          </label>
        ))}
      </fieldset>
      {sessionLog && (
        <section className="session-log" aria-label="Registro de la sesión">
          <h3>Registro de la sesión</h3>
          {sessionLog.length === 0 ? <p className="detail">Sin eventos todavía.</p> : (
            <ul className="detail">{sessionLog.map(line => <li key={line}>{line}</li>)}</ul>
          )}
        </section>
      )}
      {experimental && (
        <fieldset className="experimental">
          <legend>Funciones experimentales</legend>
          <label>
            <input type="checkbox" checked={experimental.winProb} onChange={e => experimental.onWinProb(e.target.checked)} />
            {' '}Probabilidad de victoria (experimental)
          </label>
        </fieldset>
      )}
      {note && <p role={note.error ? 'alert' : 'status'} className={note.error ? 'status error' : 'detail'}>{note.text}</p>}
    </section>
  )
}
