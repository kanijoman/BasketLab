/**
 * Transport bar of the demo (issue #231): the match in its own row with the crests, play/pause and restart as icon buttons, the speed
 * as a segmented control, a timeline to seek (elapsed / total) and, below, what the (recorded) feed is doing.
 */
import { useState } from 'react'
import { Pause, Play, RotateCcw, SkipForward } from 'lucide-react'
import type { RecordingFrame, TeamRef } from '../engine/types'
import TeamLogo from './TeamLogo'

/** 'sample' = the bundled sample game; otherwise the code of a recorded match. */
export type DemoSource = string
export const SAMPLE = 'sample'
export const SPEEDS = [1, 10, 30, 60, 300]

/** A jump forward longer than this skips alerts, so it asks first; any jump back asks (it rebuilds the engine and clears the alerts). */
export const SEEK_FORWARD_FREE_S = 120

export const mmss = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`

interface Props {
  source: DemoSource
  /** The name of the match that is playing (the matches are chosen in the Partidos tab, issue #476). */
  title: string
  playing: boolean
  onPlay: () => void
  finished: boolean
  speed: number
  onSpeed: (speed: number) => void
  onRestart: () => void
  /** Jump to a game-second (going back rebuilds the engine from the start). */
  onSeek: (to: number) => void
  /** Jump to the next moment with something new (a recorded match that lists its events; absent: no button, issue #345). */
  onNextEvent?: () => void
  hasNextEvent?: boolean
  ms: number | null
  /** What the recorded feed did at the last step (only for the real match). */
  feed: RecordingFrame['feed']
  elapsed: number
  duration: number | null
  /** The two teams of the match shown, home first (their crests flank the selector). */
  home?: TeamRef | null
  away?: TeamRef | null
}

type Question = { kind: 'restart' } | { kind: 'seek'; to: number }

/** Inline question for what cannot be undone (issue #309): the transport bar sits where the thumb scrolls, so a stray touch must not
 *  restart or jump the match. */
function Confirm({ question, elapsed, onYes, onNo }: { question: Question; elapsed: number; onYes: () => void; onNo: () => void }) {
  const restart = question.kind === 'restart'
  const to = question.kind === 'seek' ? question.to : 0
  return (
    <div role="group" aria-label="Confirmar" className="confirm">
      {restart ? (
        <p>¿Reiniciar el partido? Se perderán las alertas que hay en pantalla.</p>
      ) : (
        <p>
          Saltar a {mmss(to)}.{' '}
          {to < elapsed ? 'Volver atrás borra las alertas que hay en pantalla.' : 'No se muestran las alertas del tramo que te saltas.'}
        </p>
      )}
      <div className="confirm-buttons">
        <button onClick={onYes}>{restart ? 'Sí, reiniciar' : 'Saltar'}</button>
        <button className="secondary" onClick={onNo}>Cancelar</button>
      </div>
    </div>
  )
}

export default function DemoControls(p: Props) {
  const total = p.duration ?? 0
  const [drag, setDrag] = useState<number | null>(null)
  const [question, setQuestion] = useState<Question | null>(null)
  /** Bumped to remount the range input: on some devices the native thumb stays where it was dragged although the value did not change (#472). */
  const [syncKey, setSyncKey] = useState(0)
  const resync = () => { setDrag(null); setSyncKey(k => k + 1) }

  /** The timeline commits when it is released, not while it moves: a touch to stop the scrolling must not jump the match. */
  const commitSeek = () => {
    if (drag === null) return
    const to = drag
    setDrag(null)
    if (to === Math.floor(p.elapsed)) return
    if (to < p.elapsed || to - p.elapsed > SEEK_FORWARD_FREE_S) setQuestion({ kind: 'seek', to })
    else p.onSeek(to)
  }
  const answer = (yes: boolean) => {
    const q = question
    setQuestion(null)
    resync()
    if (!yes || !q) return
    if (q.kind === 'restart') p.onRestart()
    else p.onSeek(q.to)
  }
  return (
    <section className="transport" aria-label="Reproducción">
      <div className="transport-source" role="group" aria-label="Partido de la demostración">
        {p.home && <TeamLogo team={p.home} size={32} />}
        <strong className="transport-title">{p.title}</strong>
        {p.away && <TeamLogo team={p.away} size={32} />}
      </div>

      <div className="transport-buttons">
        <button className="icon-button" aria-label={p.playing ? 'Pausa' : 'Reproducir'} onClick={p.onPlay} disabled={p.finished}>
          {p.playing ? <Pause size={22} aria-hidden="true" /> : <Play size={22} aria-hidden="true" />}
        </button>
        {p.onNextEvent && (
          <button className="icon-button secondary" aria-label="Siguiente evento" onClick={p.onNextEvent} disabled={!p.hasNextEvent}>
            <SkipForward size={20} aria-hidden="true" />
          </button>
        )}
        <button className="icon-button secondary" aria-label="Reiniciar" onClick={() => (p.elapsed > 0 ? setQuestion({ kind: 'restart' }) : p.onRestart())}>
          <RotateCcw size={20} aria-hidden="true" />
        </button>
        <div className="segmented" role="radiogroup" aria-label="Velocidad">
          {SPEEDS.map(s => (
            <button key={s} role="radio" aria-checked={s === p.speed} className={s === p.speed ? 'segment selected' : 'segment'}
              onClick={() => p.onSpeed(s)}>{s}×</button>
          ))}
        </div>
      </div>

      <div className="timeline">
        <input key={syncKey} type="range" aria-label="Línea de tiempo" min={0} max={total} step={1} value={drag ?? Math.min(p.elapsed, total)}
          disabled={p.duration === null} onChange={e => { if (!question) setDrag(Number(e.target.value)) }}
          onPointerUp={commitSeek} onPointerCancel={resync} onKeyUp={commitSeek} onBlur={commitSeek} />
        <span className="timeline-time">{mmss(p.elapsed)} / {p.duration === null ? '—' : mmss(p.duration)}</span>
      </div>

      {question && <Confirm question={question} elapsed={p.elapsed} onYes={() => answer(true)} onNo={() => answer(false)} />}

      {p.source !== SAMPLE && p.feed === 'waiting' && <p className="status">Esperando el inicio del partido…</p>}
      {p.source !== SAMPLE && p.feed === 'gap' && (
        <p className="status warn">FEB no responde (404): se mantiene el último estado.</p>
      )}
      {p.ms !== null && <p className="perf">{p.ms} ms</p>}
    </section>
  )
}
