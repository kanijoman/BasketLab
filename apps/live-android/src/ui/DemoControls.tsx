/** Controls of the demo: which match is replayed, play / pause, speed, restart, and what the (recorded) feed is doing. */
import type { RecordingFrame } from '../engine/types'

export type DemoSource = 'sample' | 'real'
export const SPEEDS = [1, 10, 30, 60, 300]

export const SOURCES: { value: DemoSource; label: string }[] = [
  { value: 'sample', label: 'Partido de ejemplo' },
  { value: 'real', label: 'Partido real: Zamora – León' },
]

const mmss = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`

interface Props {
  source: DemoSource
  onSource: (source: DemoSource) => void
  playing: boolean
  onPlay: () => void
  finished: boolean
  speed: number
  onSpeed: (speed: number) => void
  onRestart: () => void
  ms: number | null
  /** What the recorded feed did at the last step (only for the real match). */
  feed: RecordingFrame['feed']
  elapsed: number
  duration: number | null
}

export default function DemoControls(p: Props) {
  return (
    <>
      <section className="controls">
        <button onClick={p.onPlay} disabled={p.finished}>{p.playing ? 'Pausa' : 'Reproducir'}</button>
        <label>
          Velocidad
          <select value={p.speed} onChange={e => p.onSpeed(Number(e.target.value))}>
            {SPEEDS.map(s => <option key={s} value={s}>{s}×</option>)}
          </select>
        </label>
        <label className="demo-source">
          Partido de la demostración
          <select value={p.source} onChange={e => p.onSource(e.target.value as DemoSource)}>
            {SOURCES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
        <button className="secondary" onClick={p.onRestart}>Reiniciar</button>
        {p.ms !== null && <span className="perf">{p.ms} ms</span>}
      </section>

      {p.source === 'real' && p.duration !== null && (
        <p className="detail">Grabación real: {mmss(p.elapsed)} de {mmss(p.duration)}</p>
      )}
      {p.source === 'real' && p.feed === 'waiting' && <p className="status">Esperando el inicio del partido…</p>}
      {p.source === 'real' && p.feed === 'gap' && (
        <p className="status warn">FEB no responde (404): se mantiene el último estado.</p>
      )}
    </>
  )
}
