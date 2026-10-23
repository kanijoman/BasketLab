import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import RemoveButton from './RemoveButton'

afterEach(cleanup)

describe('RemoveButton: deleting a saved match asks first (issue #512)', () => {
  it('«Eliminar» only asks: nothing is deleted until the user confirms', () => {
    const onConfirm = vi.fn()
    render(<RemoveButton what="LEON – UNIBASKET" onConfirm={onConfirm} />)
    fireEvent.click(screen.getByRole('button', { name: /eliminar leon – unibasket/i }))
    expect(onConfirm).not.toHaveBeenCalled()
    expect(screen.getByText(/se borra de este dispositivo/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /sí, eliminar/i }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('cancelling leaves everything as it was and the question goes away', () => {
    const onConfirm = vi.fn()
    render(<RemoveButton what="LEON – UNIBASKET" onConfirm={onConfirm} />)
    fireEvent.click(screen.getByRole('button', { name: /eliminar leon/i }))
    fireEvent.click(screen.getByRole('button', { name: /cancelar/i }))
    expect(onConfirm).not.toHaveBeenCalled()
    expect(screen.queryByText(/se borra de este dispositivo/i)).toBeNull()
    expect(screen.getByRole('button', { name: /eliminar leon/i })).toBeTruthy()
  })

  it('can be disabled (a live connection is running)', () => {
    render(<RemoveButton what="X" onConfirm={vi.fn()} disabled />)
    expect((screen.getByRole('button', { name: /eliminar x/i }) as HTMLButtonElement).disabled).toBe(true)
  })
})
