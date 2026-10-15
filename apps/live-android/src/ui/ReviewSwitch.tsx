/** With a package loaded: follow its match live, or review the recorded matches (Zamora–León and the sample game) without losing the package (issue #344). */
interface Props {
  reviewing: boolean
  /** A live connection is running: leaving it would drop the match being followed. */
  disabled: boolean
  onLive: () => void
  onReview: () => void
}

export default function ReviewSwitch({ reviewing, disabled, onLive, onReview }: Props) {
  return (
    <fieldset className="review-switch" role="radiogroup" aria-label="Qué partido ver">
      <legend>Qué partido ver</legend>
      <label>
        <input type="radio" name="which-match" checked={!reviewing} disabled={disabled} onChange={onLive} />
        <span>Partido del paquete</span>
      </label>
      <label>
        <input type="radio" name="which-match" checked={reviewing} disabled={disabled} onChange={onReview} />
        <span>Revisar partidos grabados</span>
      </label>
      {disabled && <p className="detail">Desconecta antes de revisar un partido grabado.</p>}
      {reviewing && <p className="detail">Estás revisando un partido grabado. Tu paquete sigue guardado: vuelve a «Partido del paquete» cuando quieras.</p>}
    </fieldset>
  )
}
