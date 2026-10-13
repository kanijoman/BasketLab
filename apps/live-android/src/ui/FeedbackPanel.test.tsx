import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import FeedbackPanel from './FeedbackPanel'

const RECORDS = [
  { key: 'a', id: 'x', severity: 'warning', category: 'rotacion', elapsed: 1, shown_at: 't', verdict: 'seguida', decided_at: 't' },
  { key: 'b', id: 'y', severity: 'info', category: 'rival', elapsed: 2, shown_at: 't', verdict: null, decided_at: null },
] as const

const exportJson = () => '{"v":1}'

afterEach(() => vi.unstubAllGlobals())

describe('FeedbackPanel (issue #235)', () => {
  it('says how many alerts have an answer', () => {
    render(<FeedbackPanel records={[...RECORDS]} exportJson={exportJson} fileName="f.json" onClear={() => undefined} />)
    expect(screen.getByText(/1 de 2 alertas valoradas/i)).toBeTruthy()
  })

  it('copies the export to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    render(<FeedbackPanel records={[...RECORDS]} exportJson={exportJson} fileName="f.json" onClear={() => undefined} />)
    fireEvent.click(screen.getByRole('button', { name: 'Copiar' }))
    await waitFor(() => expect(screen.getByText('Copiado')).toBeTruthy())
    expect(writeText).toHaveBeenCalledWith('{"v":1}')
  })

  it('says so when the clipboard is not available instead of failing silently', async () => {
    vi.stubGlobal('navigator', {})
    render(<FeedbackPanel records={[...RECORDS]} exportJson={exportJson} fileName="f.json" onClear={() => undefined} />)
    fireEvent.click(screen.getByRole('button', { name: 'Copiar' }))
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/no se pudo copiar/i))
  })

  it('downloads a JSON file named after the match', () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:x')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    render(<FeedbackPanel records={[...RECORDS]} exportJson={exportJson} fileName="feedback-live-1.json" onClear={() => undefined} />)
    fireEvent.click(screen.getByRole('button', { name: 'Descargar' }))
    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect((createObjectURL.mock.calls[0][0] as Blob).type).toBe('application/json')
    expect(click).toHaveBeenCalledTimes(1)
    click.mockRestore()
  })

  it('asks before clearing and clears on confirmation', () => {
    const onClear = vi.fn()
    render(<FeedbackPanel records={[...RECORDS]} exportJson={exportJson} fileName="f.json" onClear={onClear} />)
    fireEvent.click(screen.getByRole('button', { name: 'Borrar' }))
    expect(onClear).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar borrado' }))
    expect(onClear).toHaveBeenCalledTimes(1)
  })
})
