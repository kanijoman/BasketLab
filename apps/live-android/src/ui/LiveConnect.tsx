/** Live mode of the app: connect to the federation (FEB or FBCYL, whichever the match belongs to) for the match of the loaded package and see what the connection is doing. */
import { useEffect, useState } from 'react'
import { lagText, type LagSummary } from '../feed/feedLag'
import { isConnectable, shownCode, sourceOf, type FeedSource } from '../feed/feedSource'
import type { FeedState } from '../feed/liveFeed'
import HelpHint from './HelpHint'

interface Props {
  /** Code of the match the package was prepared for: FEB's digits or a FBCYL code (null: the user types a FEB code). */
  matchCode: string | null
  state: FeedState
  running: boolean
  /** Whether the screen is being kept on while connected (null: not connected). */
  awake?: boolean | null
  /** How late the data of the federation is on this connection (issue #411; FBCYL gives nothing to measure it with). */
  lag?: LagSummary | null
  onStart: (code: string) => void
  onStop: () => void
}

function ago(ms: number): string {
  const seconds = Math.max(0, Math.round(ms / 1000))
  return seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)} min`
}

/** Re-renders every second while a "last data" age is on screen. */
function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [active])
  return now
}

function Status({ state, now, source }: { state: FeedState; now: number; source: FeedSource }) {
  switch (state.kind) {
    case 'connecting': return <p className="status">Conectando con {source}…</p>
    case 'waiting': return <p className="status">Esperando el inicio del partido…</p>
    case 'live': return <p className="status">En directo · último dato hace {ago(now - state.lastOkAt)}</p>
    case 'gap':
      return (
        <p className="status warn">
          {state.message ?? `${source} no responde`}: se mantiene el último estado.
          {state.lastOkAt !== null ? ` Último dato hace ${ago(now - state.lastOkAt)}.` : ''}
        </p>
      )
    case 'finished': return <p className="status">Partido finalizado</p>
    case 'stopped': return <p className="status">Desconectado</p>
    default: return null
  }
}

export default function LiveConnect({ matchCode, state, running, awake = null, lag = null, onStart, onStop }: Props) {
  const [typed, setTyped] = useState('')
  const now = useNow(state.kind === 'live' || state.kind === 'gap')
  const code = (matchCode ?? typed).trim()
  const valid = isConnectable(code)
  const source = sourceOf(code)

  return (
    <section className="panel" aria-label="Partido en directo">
      <h2>Partido en directo</h2>
      {state.kind === 'idle' && <p className="detail">Paquete cargado. Conecta con {source} cuando empiece el partido.</p>}
      {matchCode ? (
        <p className="detail">Partido de {source}: <strong>{shownCode(matchCode)}</strong></p>
      ) : (
        <label>
          Código del partido (FEB)
          <input inputMode="numeric" value={typed} onChange={e => setTyped(e.target.value)} placeholder="p. ej. 2524475" />
        </label>
      )}
      {!matchCode && (
        <HelpHint label="Ayuda sobre el código">
          Es el número que aparece en la dirección del partido en la web de FEB (por ejemplo, 2524475). Los paquetes
          descargados de la lista ya lo traen y no hace falta escribirlo.
        </HelpHint>
      )}
      <Status state={state} now={now} source={source} />
      {running && lag && lagText(lag) && <p className="detail">{lagText(lag)}</p>}
      {running && awake === true && <p className="detail">Pantalla encendida mientras dure la conexión.</p>}
      {running && awake === false && (
        <p className="status warn">No se pudo mantener la pantalla encendida: desactiva el bloqueo automático de la tablet durante el partido.</p>
      )}
      {running
        ? <button className="secondary" onClick={onStop}>Desconectar</button>
        : <button disabled={!valid} onClick={() => onStart(code)}>Conectar con {source}</button>}
    </section>
  )
}
