/** Live mode of the app: connect to FEB for the match of the loaded package and see what the connection is doing. */
import { useEffect, useState } from 'react'
import type { FeedState } from '../feed/liveFeed'

interface Props {
  /** FEB match code the package was prepared for (null: the user types it). */
  matchCode: string | null
  state: FeedState
  running: boolean
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

function Status({ state, now }: { state: FeedState; now: number }) {
  switch (state.kind) {
    case 'connecting': return <p className="status">Conectando con FEB…</p>
    case 'waiting': return <p className="status">Esperando el inicio del partido…</p>
    case 'live': return <p className="status">En directo · último dato hace {ago(now - state.lastOkAt)}</p>
    case 'gap':
      return (
        <p className="status warn">
          {state.message ?? 'FEB no responde'}: se mantiene el último estado.
          {state.lastOkAt !== null ? ` Último dato hace ${ago(now - state.lastOkAt)}.` : ''}
        </p>
      )
    case 'finished': return <p className="status">Partido finalizado</p>
    case 'stopped': return <p className="status">Desconectado</p>
    default: return null
  }
}

export default function LiveConnect({ matchCode, state, running, onStart, onStop }: Props) {
  const [typed, setTyped] = useState('')
  const now = useNow(state.kind === 'live' || state.kind === 'gap')
  const code = (matchCode ?? typed).trim()
  const valid = /^\d+$/.test(code)

  return (
    <section className="panel" aria-label="Partido en directo">
      <h2>Partido en directo</h2>
      {state.kind === 'idle' && <p className="detail">Paquete cargado. Conecta con FEB cuando empiece el partido.</p>}
      {matchCode ? (
        <p className="detail">Partido de FEB: <strong>{matchCode}</strong></p>
      ) : (
        <label>
          Código del partido (FEB)
          <input inputMode="numeric" value={typed} onChange={e => setTyped(e.target.value)} placeholder="p. ej. 2524475" />
        </label>
      )}
      <Status state={state} now={now} />
      {running
        ? <button className="secondary" onClick={onStop}>Desconectar</button>
        : <button disabled={!valid} onClick={() => onStart(code)}>Conectar con FEB</button>}
    </section>
  )
}
