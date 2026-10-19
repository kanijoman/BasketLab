import type { SavedRecording } from '../feed/recordingStore'

/** The recordings of the matches followed live that are kept on the device (issue #416): each can be shared as a file to replay it. */
interface Props {
  recordings: SavedRecording[]
  onShare: (code: string) => void
}

const date = (iso: string) => new Date(iso).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' })

export default function RecordingsPanel({ recordings, onShare }: Props) {
  if (recordings.length === 0) return null
  return (
    <section className="panel recordings" aria-label="Grabaciones del partido en directo">
      <h2>Grabaciones del directo</h2>
      <p className="detail">La app graba lo que recibe de FEB mientras sigues un partido. Compártela para tener los datos completos aunque la grabación del servidor llegue tarde.</p>
      <ul className="remote-packages">
        {recordings.map(r => (
          <li key={r.code}>
            <span>
              {r.title} <span className="detail">· {date(r.savedAt)} · {r.complete ? 'completa' : 'incompleta'} · {r.frames} documentos</span>
            </span>
            <button type="button" className="secondary" aria-label={`Compartir grabación de ${r.title}`} onClick={() => onShare(r.code)}>
              Compartir grabación
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
