/**
 * AccessPanel — pide la invitación cuando un contenido está sellado y el navegador no tiene clave que lo abra (issue #639).
 * La invitación (enlace o clave) se guarda solo en este navegador; no hay cuentas. Mientras dure la beta no hace falta: la clave abierta va en el
 * manifiesto y la web la usa sola.
 */
import { useState, type FormEvent } from 'react'
import { KeyRound } from 'lucide-react'

import { addRight } from '@live-package/rights'
import { parseWebInvite } from '@/webdata/invite'
import Button from '@/components/ui/Button'
import EmptyState from '@/components/ui/EmptyState'
import { Field, Input } from '@/components/ui/Field'

interface Props {
  /** Called once the invitation is kept, to read the content again. */
  onUnlocked: () => void
}

export default function AccessPanel({ onUnlocked }: Props) {
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)

  function unlock(event: FormEvent) {
    event.preventDefault()
    try {
      addRight(parseWebInvite(text))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo usar la invitación.')
      return
    }
    setError(null)
    setText('')
    onUnlocked()
  }

  return (
    <div className="card">
      <EmptyState
        icon={KeyRound}
        title="Este informe necesita una invitación"
        description="Pega el enlace o la clave que te enviaron. Se guarda solo en este navegador y no hace falta iniciar sesión."
        action={
          <form onSubmit={unlock} className="flex w-full max-w-md flex-col gap-3 text-left">
            <Field label="Invitación" error={error ?? undefined}>
              <Input value={text} onChange={e => setText(e.target.value)} placeholder="https://…#invite=bl1.… o bl1.…" autoComplete="off" spellCheck={false} />
            </Field>
            <Button type="submit" disabled={!text.trim()}>Desbloquear</Button>
          </form>
        }
      />
    </div>
  )
}
