import type { SavedRecording } from '../feed/recordingStore'
import RemoveButton from './RemoveButton'

/** The recordings of the matches followed live that are kept on the device (issue #416): each can be shared as a file to replay it. */
interface Props {
  recordings: SavedRecording[]
  onShare: (code: string) => void
  /** Deletes a recording (issue #512; the button asks first). */
  onRemove: (code: string) => void
}

const date = (iso: string) => new Date(iso).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' })

export default function RecordingsPanel({ recordings, onShare, onRemove }: Props) {
  if (recordings.length === 0) return null
  return (
    <section className="panel recordings" aria-label="Grabaciones del partido en directo">
      <h2>Grabaciones del directo</h2>
      <p className="detail">La app graba lo que recibe de FEB mientras sigues un partido. Compártela para tener los datos completos aunque la grabación del servidor llegue tarde.</p>
      <ul className="remote-packages">
        {recordings.map(r => (
          <li key={r.code}>
            <span className="round-info">
              <strong className="match-title">{r.title}</strong>
              <span className="detail round-when">{date(r.savedAt)} · {r.complete ? 'completa' : 'incompleta'} · {r.frames} documentos</span>
            </span>
            <span className="round-sides">
              <button type="button" className="secondary" aria-label={`Compartir grabación de ${r.title}`} onClick={() => onShare(r.code)}>
                Compartir
              </button>
              <RemoveButton what={`grabación de ${r.title}`} onConfirm={() => onRemove(r.code)} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
