import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import HelpHint from './HelpHint'
import LiveConnect from './LiveConnect'
import PackagePanel from './PackagePanel'
import type { PackageStore } from '../package/storage'
import type { EngineApi } from '../engine/client'

describe('HelpHint (issue #225)', () => {
  it('hides the text until the button is pressed, and hides it again', () => {
    render(<HelpHint label="Ayuda sobre algo">Texto de ayuda</HelpHint>)
    const button = screen.getByRole('button', { name: 'Ayuda sobre algo' })
    expect(button.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByText('Texto de ayuda')).toBeNull()
    fireEvent.click(button)
    expect(button.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByRole('note').textContent).toBe('Texto de ayuda')
    fireEvent.click(button)
    expect(screen.queryByText('Texto de ayuda')).toBeNull()
  })
})

const store: PackageStore = { load: async () => null, save: async () => undefined, clear: async () => undefined }
const engine = {} as EngineApi

describe('help texts of the Paquetes tab and the live connection (issue #225)', () => {
  it('the package panel explains what the preparation package is and when to import a file', () => {
    render(<PackagePanel engine={engine} store={store} onLoaded={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /ayuda sobre el paquete de preparación/i }))
    expect(screen.getByRole('note').textContent).toMatch(/estadísticas de la temporada/i)
    expect(screen.getByRole('note').textContent).toMatch(/3 veces al día/i)
    // the import of a file explains itself in its folded option (issue #338), not behind a «?»
    expect(screen.getByText(/importar un fichero \.bpkg \(sin conexión/i)).toBeTruthy()
  })

  it('the live connection explains the match code', () => {
    render(<LiveConnect matchCode={null} state={{ kind: 'idle' }} running={false} onStart={vi.fn()} onStop={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /ayuda sobre el código/i }))
    expect(screen.getByRole('note').textContent).toMatch(/número que aparece en la dirección/i)
  })
})
