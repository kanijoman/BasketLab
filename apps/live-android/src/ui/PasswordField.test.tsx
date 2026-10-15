import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import PasswordField from './PasswordField'

function Host({ initial = '' }: { initial?: string }) {
  const [value, setValue] = useState(initial)
  return <PasswordField label="Contraseña de prueba" value={value} onChange={setValue} />
}

// Issue #337: nothing told the staff what they had typed on the phone keyboard
describe('PasswordField (issue #337)', () => {
  it('hides the password and a button shows it and hides it again', () => {
    render(<Host initial="secreto" />)
    const input = screen.getByLabelText('Contraseña de prueba') as HTMLInputElement
    expect(input.type).toBe('password')
    const toggle = screen.getByRole('button', { name: /mostrar contraseña/i })
    expect(toggle.getAttribute('aria-pressed')).toBe('false')
    fireEvent.click(toggle)
    expect(input.type).toBe('text')
    expect(screen.getByRole('button', { name: /ocultar contraseña/i }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: /ocultar contraseña/i }))
    expect(input.type).toBe('password')
  })

  it('the phone keyboard does not capitalise, correct or suggest what is typed', () => {
    render(<Host />)
    const input = screen.getByLabelText('Contraseña de prueba')
    expect(input.getAttribute('autocapitalize')).toBe('off')
    expect(input.getAttribute('autocorrect')).toBe('off')
    expect(input.getAttribute('spellcheck')).toBe('false')
    expect(input.getAttribute('autocomplete')).toBe('off')
  })

  it('the typed value goes up', () => {
    render(<Host />)
    fireEvent.change(screen.getByLabelText('Contraseña de prueba'), { target: { value: 'abc' } })
    expect((screen.getByLabelText('Contraseña de prueba') as HTMLInputElement).value).toBe('abc')
  })
})
