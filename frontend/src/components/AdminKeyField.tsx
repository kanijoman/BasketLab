/** Input for the admin API key required by destructive / ingestion / training endpoints. */
import { useState } from 'react'
import { KeyRound } from 'lucide-react'
import { clearAdminKey, getAdminKey, setAdminKey } from '@/lib/adminKey'

export default function AdminKeyField() {
  const [value, setValue] = useState('')
  const [saved, setSaved] = useState(() => Boolean(getAdminKey()))

  function save() {
    setAdminKey(value)
    setSaved(Boolean(getAdminKey()))
    setValue('')
  }

  function remove() {
    clearAdminKey()
    setSaved(false)
  }

  return (
    <div className="card p-4 flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1 text-xs text-ink-secondary flex-1 min-w-[220px]">
        <span className="flex items-center gap-1.5"><KeyRound className="w-3.5 h-3.5" /> Clave de administración</span>
        <input
          type="password"
          value={value}
          onChange={e => setValue(e.target.value)}
          autoComplete="off"
          placeholder={saved ? '••••••••' : 'Necesaria para borrar, descargar datos y entrenar modelos'}
          className="bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400"
        />
      </label>
      <button className="btn-secondary" onClick={save} disabled={!value.trim()}>Guardar</button>
      {saved && (
        <>
          <span className="text-xs text-up">Clave guardada (solo esta sesión del navegador)</span>
          <button className="btn-secondary" onClick={remove}>Quitar</button>
        </>
      )}
    </div>
  )
}
