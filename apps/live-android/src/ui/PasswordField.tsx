/** A password input made for a phone keyboard (issue #337): no capital letter, correction or suggestion, and a button to see what was typed. */
import { useState } from 'react'

interface Props {
  label: string
  value: string
  onChange: (value: string) => void
  /** Class of the label (the styles of each panel). */
  className?: string
}

export default function PasswordField({ label, value, onChange, className }: Props) {
  const [shown, setShown] = useState(false)
  return (
    <div className="password-field">
      <label className={className}>
        {label}
        <input type={shown ? 'text' : 'password'} value={value} onChange={e => onChange(e.target.value)}
          autoComplete="off" autoCapitalize="off" autoCorrect="off" spellCheck={false} />
      </label>
      <button type="button" className="secondary" aria-pressed={shown} onClick={() => setShown(s => !s)}>
        {shown ? 'Ocultar contraseña' : 'Mostrar contraseña'}
      </button>
    </div>
  )
}
