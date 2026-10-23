/** Deleting a match kept on the device (issue #512): the button asks first, a stray touch on a phone must not lose a ~1 MB saved match. */
import { useState } from 'react'

interface Props {
  /** What is deleted, for the accessible name: «Eliminar LEON – UNIBASKET». */
  what: string
  onConfirm: () => void
  disabled?: boolean
}

export default function RemoveButton({ what, onConfirm, disabled }: Props) {
  const [asking, setAsking] = useState(false)
  if (!asking) {
    return <button type="button" className="secondary" aria-label={`Eliminar ${what}`} disabled={disabled} onClick={() => setAsking(true)}>Eliminar</button>
  }
  return (
    <span className="confirm-remove" role="group" aria-label="Confirmar">
      <span className="detail">Se borra de este dispositivo y no se puede recuperar.</span>
      <button type="button" onClick={() => { setAsking(false); onConfirm() }}>Sí, eliminar</button>
      <button type="button" className="secondary" onClick={() => setAsking(false)}>Cancelar</button>
    </span>
  )
}
