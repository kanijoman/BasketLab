/** Input for the admin API key required by destructive / ingestion / training endpoints. */
import { useState } from 'react'
import { KeyRound } from 'lucide-react'
import { clearAdminKey, getAdminKey, setAdminKey } from '@/lib/adminKey'
import Button from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'

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
      <Field className="flex-1 min-w-[220px]" label={<span className="flex items-center gap-1.5"><KeyRound className="w-3.5 h-3.5" aria-hidden="true" /> Clave de administración</span>}>
        <Input
          type="password"
          value={value}
          onChange={e => setValue(e.target.value)}
          autoComplete="off"
          placeholder={saved ? '••••••••' : 'Necesaria para borrar, descargar datos y entrenar modelos'}
        />
      </Field>
      <Button variant="secondary" onClick={save} disabled={!value.trim()}>Guardar</Button>
      {saved && (
        <>
          <span className="text-xs text-ok">Clave guardada (solo esta sesión del navegador)</span>
          <Button variant="secondary" onClick={remove}>Quitar</Button>
        </>
      )}
    </div>
  )
}
