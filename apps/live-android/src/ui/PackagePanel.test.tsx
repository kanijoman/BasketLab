import { webcrypto } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PackagePanel from './PackagePanel'
import type { PackageStore, StoredPackage } from '../package/storage'
import type { EngineApi } from '../engine/client'

const repoRoot = path.resolve(import.meta.dirname, '../../../..')
const fixture = fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo.bpkg'), 'utf8')
const demoPackage: string = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/vectors.json'), 'utf8')).engine.package
const PASS = 'clave-de-prueba-1'

const META = {
  package_id: 'p', schema_version: 1, created_at: '2026-01-01T00:00:00Z', collection: 'c', season: '2025-2026',
  team: { id: '982047', name: 'ACEITES ABRIL ADBA SANFER' }, rival: { id: '981204', name: 'MANRESA CBF A' },
}

function memoryStore(initial: StoredPackage | null = null): PackageStore & { saved: StoredPackage | null } {
  const s = {
    saved: initial,
    load: async () => s.saved,
    save: async (r: StoredPackage) => { s.saved = r },
    clear: async () => { s.saved = null },
  }
  return s
}

function engineStub(over: Partial<EngineApi> = {}): EngineApi {
  return { start: vi.fn().mockResolvedValue(META), loadReplay: vi.fn(), replay: vi.fn(), update: vi.fn(), dispose: vi.fn(), ...over } as EngineApi
}

const file = (text: string, name = 'live.bpkg') => new File([text], name, { type: 'application/octet-stream' })

async function importFile(text: string, pass: string) {
  fireEvent.change(screen.getByLabelText(/contraseña del paquete/i), { target: { value: pass } })
  fireEvent.change(screen.getByLabelText(/fichero del paquete/i), { target: { files: [file(text)] } })
  fireEvent.click(screen.getByRole('button', { name: /importar/i }))
}

beforeEach(() => vi.stubGlobal('crypto', webcrypto))

describe('PackagePanel', () => {
  it('imports an encrypted package: decrypts, validates with the engine, stores it and reports it', async () => {
    const store = memoryStore()
    const engine = engineStub()
    const onLoaded = vi.fn()
    render(<PackagePanel engine={engine} store={store} onLoaded={onLoaded} />)
    await importFile(fixture, PASS)
    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
    expect(engine.start).toHaveBeenCalledWith(demoPackage)
    expect(store.saved?.plaintext).toBe(demoPackage)
    expect(onLoaded.mock.calls[0][0]).toMatchObject({ team: 'ACEITES ABRIL ADBA SANFER', rival: 'MANRESA CBF A' })
  })

  it('shows an error for a wrong password and does not store anything', async () => {
    const store = memoryStore()
    render(<PackagePanel engine={engineStub()} store={store} onLoaded={vi.fn()} />)
    await importFile(fixture, 'contraseña-incorrecta')
    expect(await screen.findByText(/contraseña/i, { selector: '[role="alert"]' })).toBeTruthy()
    expect(store.saved).toBeNull()
  })

  it('shows the engine error when the package is corrupted or incompatible', async () => {
    const engine = engineStub({ start: vi.fn().mockRejectedValue(new Error('Package checksum mismatch')) })
    const store = memoryStore()
    render(<PackagePanel engine={engine} store={store} onLoaded={vi.fn()} />)
    await importFile(fixture, PASS)
    expect(await screen.findByText(/checksum mismatch/i)).toBeTruthy()
    expect(store.saved).toBeNull()
  })

  it('requires a file and a password before importing', () => {
    render(<PackagePanel engine={engineStub()} store={memoryStore()} onLoaded={vi.fn()} />)
    expect(screen.getByRole('button', { name: /importar/i })).toBeDisabled()
  })

  it('shows the loaded package summary and lets the user remove it', async () => {
    const store = memoryStore({ plaintext: demoPackage, savedAt: '2026-10-09T10:00:00Z' })
    const onRemoved = vi.fn()
    render(<PackagePanel engine={engineStub()} store={store} loaded={{
      team: 'ACEITES ABRIL ADBA SANFER', rival: 'MANRESA CBF A', season: '2025-2026', collection: 'c',
      createdAt: '2026-01-01T00:00:00Z', ownPlayers: 12, rivalPlayers: 9, games: { own: 1, rival: 1, league: 1 }, match: null,
    }} onLoaded={vi.fn()} onRemoved={onRemoved} />)
    expect(screen.getByText(/ACEITES ABRIL ADBA SANFER/)).toBeTruthy()
    expect(screen.getByText(/MANRESA CBF A/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /quitar paquete/i }))
    await waitFor(() => expect(onRemoved).toHaveBeenCalled())
    expect(store.saved).toBeNull()
  })

  it('shows the match the package is for', () => {
    render(<PackagePanel engine={engineStub()} store={memoryStore()} loaded={{
      team: 'A', rival: 'B', season: '2026', collection: 'c', createdAt: '2026-10-08T12:00:00Z', ownPlayers: 1, rivalPlayers: 1,
      games: { own: 1, rival: 1, league: 1 },
      match: { code: '2524465', start: '2026-10-10T19:00', home: { id: '1', name: 'A' }, away: { id: '2', name: 'B' } },
    }} onLoaded={vi.fn()} />)
    expect(screen.getByText(/código 2524465/i)).toBeTruthy()
    expect(screen.getByText(/10\/10\/2026/)).toBeTruthy()
  })
})
