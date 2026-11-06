import fs from 'node:fs'
import path from 'node:path'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import PackagePanel from './PackagePanel'
import type { PackageStore, StoredPackage } from '../package/storage'

const repoRoot = path.resolve(import.meta.dirname, '../../../..')
const demoPackage: string = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/vectors.json'), 'utf8')).engine.package

function memoryStore(initial: StoredPackage | null = null): PackageStore & { saved: StoredPackage | null } {
  const s = {
    saved: initial,
    load: async () => s.saved,
    save: async (r: StoredPackage) => { s.saved = r },
    clear: async () => { s.saved = null },
  }
  return s
}

// The password of the packages was removed: the panel only shows and removes the loaded package, it does not import a file any more.
describe('PackagePanel: no password and no import of a file', () => {
  it('has no file input, no password field and no import button', () => {
    const { container } = render(<PackagePanel store={memoryStore()} />)
    expect(container.querySelector('input[type="file"]')).toBeNull()
    expect(container.querySelector('input[type="password"]')).toBeNull()
    expect(container.querySelector('details.package-import')).toBeNull()
    expect(screen.queryByLabelText(/contraseña/i)).toBeNull()
    expect(screen.queryByRole('button', { name: /importar/i })).toBeNull()
  })
})

describe('PackagePanel', () => {
  it('shows the loaded package summary and lets the user remove it', async () => {
    const store = memoryStore({ plaintext: demoPackage, savedAt: '2026-10-09T10:00:00Z' })
    const onRemoved = vi.fn()
    render(<PackagePanel store={store} loaded={{
      team: 'ACEITES ABRIL ADBA SANFER', teamId: '982047', rival: 'MANRESA CBF A', rivalId: '981204', season: '2025-2026', collection: 'c',
      createdAt: '2026-01-01T00:00:00Z', ownPlayers: 12, rivalPlayers: 9, games: { own: 1, rival: 1, league: 1 }, match: null,
    }} onRemoved={onRemoved} />)
    expect(screen.getByText(/ACEITES ABRIL ADBA SANFER/)).toBeTruthy()
    expect(screen.getByText(/MANRESA CBF A/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /quitar paquete/i }))
    await waitFor(() => expect(onRemoved).toHaveBeenCalled())
    expect(store.saved).toBeNull()
  })

  it('shows the match the package is for', () => {
    render(<PackagePanel store={memoryStore()} loaded={{
      team: 'A', teamId: '1', rival: 'B', rivalId: '2', season: '2026', collection: 'c', createdAt: '2026-10-08T12:00:00Z', ownPlayers: 1, rivalPlayers: 1,
      games: { own: 1, rival: 1, league: 1 },
      match: { code: '2524465', start: '2026-10-10T19:00', home: { id: '1', name: 'A' }, away: { id: '2', name: 'B' } },
    }} />)
    expect(screen.getByText(/código 2524465/i)).toBeTruthy()
    expect(screen.getByText(/10\/10\/2026/)).toBeTruthy()
  })

  const base = { team: 'A', teamId: '1', rival: 'B', rivalId: '2', season: '2026', collection: 'c', createdAt: '2026-10-08T12:00:00Z', ownPlayers: 1, rivalPlayers: 1, games: { own: 1, rival: 1, league: 1 }, match: null }

  it('says it when the two teams are of different divisions: the prior is only approximate (#464)', () => {
    render(<PackagePanel store={memoryStore()} loaded={{ ...base, crossDivision: { own_level: 3, rival_level: 2, adjusted: 'shrink' } }} />)
    expect(screen.getByText(/equipos de divisiones distintas/i)).toBeTruthy()
  })

  it('says nothing of it when they are of the same division', () => {
    render(<PackagePanel store={memoryStore()} loaded={base} />)
    expect(screen.queryByText(/divisiones distintas/i)).toBeNull()
  })
})
