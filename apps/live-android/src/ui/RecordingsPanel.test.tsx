import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import RecordingsPanel from './RecordingsPanel'
import { REPLAY_COMPAT } from '../feed/replayCompat'

afterEach(cleanup)

describe('RecordingsPanel buttons (issue #570)', () => {
  it('a recording offers Compartir and Eliminar, and nothing else', () => {
    const rec = { code: '9', title: 'LEON – UNIBASKET', savedAt: '2026-10-17T20:30:00Z', complete: true, frames: 10, encoding: 'gzip' as const, bytes: new Uint8Array() }
    render(<RecordingsPanel recordings={[rec]} onShare={vi.fn()} onRemove={vi.fn()} />)
    const row = document.querySelector('.recordings li') as HTMLElement
    expect(Array.from(row.querySelectorAll('button')).map(b => b.textContent)).toEqual(['Compartir', 'Eliminar'])
    expect(screen.getByRole('button', { name: 'Compartir grabación de LEON – UNIBASKET' })).toBeTruthy()
  })

  it('warns about a recording kept under an older compatibility, and only about that one (issue #562)', () => {
    const rec = (code: string, extra = {}) => ({ code, title: `P${code} – Q${code}`, savedAt: '2026-10-17T20:30:00Z', complete: true, frames: 10, encoding: 'gzip' as const, bytes: new Uint8Array(), ...extra })
    render(<RecordingsPanel recordings={[rec('1', { compat: REPLAY_COMPAT }), rec('2')]} onShare={vi.fn()} onRemove={vi.fn()} />)
    const [fresh, old] = Array.from(document.querySelectorAll('.recordings li')).map(li => li.textContent ?? '')
    expect(fresh).not.toContain('versión anterior')
    expect(old).toContain('versión anterior de la app')
  })
})
