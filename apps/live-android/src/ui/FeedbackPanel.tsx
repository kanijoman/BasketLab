import { useState } from 'react'
import type { FeedbackRecord } from '../feedback/store'

interface Props {
  records: FeedbackRecord[]
  exportJson: () => string
  fileName: string
  onClear: () => void
}

/** Count of answered alerts and the ways to take the history out of the device (issue #235). */
export default function FeedbackPanel({ records, exportJson, fileName, onClear }: Props) {
  const [note, setNote] = useState<{ text: string; error: boolean } | null>(null)
  const [confirming, setConfirming] = useState(false)
  const answered = records.filter(r => r.verdict).length

  const copy = async () => {
    try {
      if (!navigator.clipboard) throw new Error('clipboard unavailable')
      await navigator.clipboard.writeText(exportJson())
      setNote({ text: 'Copiado', error: false })
    } catch {
      setNote({ text: 'No se pudo copiar: usa Descargar', error: true })
    }
  }

  const download = () => {
    const url = URL.createObjectURL(new Blob([exportJson()], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    link.click()
    URL.revokeObjectURL(url)
    setNote({ text: 'Descargado', error: false })
  }

  return (
    <section className="panel feedback-panel" aria-label="Feedback del staff">
      <h2>Feedback del staff</h2>
      <p className="detail">{answered} de {records.length} alertas valoradas</p>
      <div className="feedback-actions">
        <button type="button" className="secondary" onClick={() => void copy()}>Copiar</button>
        <button type="button" className="secondary" onClick={download}>Descargar</button>
        {confirming
          ? <button type="button" onClick={() => { setConfirming(false); setNote(null); onClear() }}>Confirmar borrado</button>
          : <button type="button" className="secondary" onClick={() => setConfirming(true)}>Borrar</button>}
      </div>
      {note && <p role={note.error ? 'alert' : 'status'} className={note.error ? 'status error' : 'detail'}>{note.text}</p>}
    </section>
  )
}
