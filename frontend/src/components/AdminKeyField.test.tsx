import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import AdminKeyField from './AdminKeyField'
import { getAdminKey } from '@/lib/adminKey'

describe('AdminKeyField', () => {
  beforeEach(() => sessionStorage.clear())

  it('saves the typed key for the session and confirms it', () => {
    render(<AdminKeyField />)
    fireEvent.change(screen.getByLabelText(/clave de administración/i), { target: { value: 'k1' } })
    fireEvent.click(screen.getByRole('button', { name: /guardar/i }))
    expect(getAdminKey()).toBe('k1')
    expect(screen.getByText(/clave guardada/i)).toBeTruthy()
  })

  it('shows as saved when a key already exists and can remove it', () => {
    sessionStorage.setItem('basketlab-admin-key', 'old')
    render(<AdminKeyField />)
    expect(screen.getByText(/clave guardada/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /quitar/i }))
    expect(getAdminKey()).toBe('')
    expect(screen.queryByText(/clave guardada/i)).toBeNull()
  })

  it('masks the key while typing', () => {
    render(<AdminKeyField />)
    expect((screen.getByLabelText(/clave de administración/i) as HTMLInputElement).type).toBe('password')
  })
})
