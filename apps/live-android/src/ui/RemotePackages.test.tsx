import { webcrypto } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RemotePackages from './RemotePackages'
import type { PackageStore, StoredPackage } from '../package/storage'
import type { EngineApi } from '../engine/client'
import { PACKAGES_BASE_URL } from '../package/remote'

const repoRoot = path.resolve(import.meta.dirname, '../../../..')
const fixture = fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo.bpkg'), 'utf8')
const demoPackage: string = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/vectors.json'), 'utf8')).engine.package
const PASS = 'clave-de-prueba-1'
const PASS_KEY = 'basketlab-live-passphrase'

async function sha(text: string) {
  const buf = await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, '0')).join('')
}

function memoryStore(): PackageStore & { saved: StoredPackage | null } {
  const s = {
    saved: null as StoredPackage | null,
    load: async () => s.saved,
    save: async (r: StoredPackage) => { s.saved = r },
    clear: async () => { s.saved = null },
  }
  return s
}
const META = { team: { id: '1', name: 'A' }, rival: { id: '2', name: 'B' } }
const engine = () => ({ start: vi.fn().mockResolvedValue(META) }) as unknown as EngineApi & { start: ReturnType<typeof vi.fn> }

async function fetcher(over: { sha?: string } = {}) {
  const index = {
    v: 1, generated_at: '2026-10-09T11:42:25+00:00',
    packages: [{
      team_id: '1008631', rival_id: '1008898', rival: 'RECOLETAS ZAMORA', file: '1008631/1008898.bpkg',
      sha256: over.sha ?? (await sha(fixture)), bytes: 100,
      match: { code: '2524470', start: '2026-10-10T17:00', round: 2, home: { id: '1008898', name: 'RECOLETAS ZAMORA' }, away: { id: '1008631', name: 'LEON' } },
    }],
  }
  return vi.fn(async (url: string) => {
    const body = url.endsWith('index.json') ? JSON.stringify(index) : fixture
    return { ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) }
  })
}

const download = () => fireEvent.click(screen.getByRole('button', { name: /descargar/i }))

beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto)
  localStorage.clear()
})

describe('RemotePackages', () => {
  it('lists the published packages with rival and date', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    expect(await screen.findByText(/RECOLETAS ZAMORA/)).toBeTruthy()
    expect(screen.getByText(/10\/10\/2026/)).toBeTruthy()
  })

  it('downloads, decrypts, installs and remembers the password', async () => {
    const store = memoryStore()
    const eng = engine()
    const onLoaded = vi.fn()
    const f = await fetcher()
    render(<RemotePackages engine={eng} store={store} onLoaded={onLoaded} fetcher={f} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: PASS } })
    download()
    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
    expect(f).toHaveBeenCalledWith(`${PACKAGES_BASE_URL}/1008631/1008898.bpkg`, expect.anything())
    expect(eng.start).toHaveBeenCalledWith(demoPackage)
    expect(store.saved?.plaintext).toBe(demoPackage)
    expect(localStorage.getItem(PASS_KEY)).toBe(PASS)
  })

  it('uses the remembered password without asking again', async () => {
    localStorage.setItem(PASS_KEY, PASS)
    const onLoaded = vi.fn()
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={onLoaded} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    download()
    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
  })

  it('a wrong password shows an error and neither installs nor remembers it', async () => {
    const store = memoryStore()
    render(<RemotePackages engine={engine()} store={store} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: 'incorrecta-123' } })
    download()
    expect(await screen.findByText(/contraseña/i, { selector: '[role="alert"]' })).toBeTruthy()
    expect(store.saved).toBeNull()
    expect(localStorage.getItem(PASS_KEY)).toBeNull()
  })

  it('offline: says so and keeps the installed package untouched', async () => {
    const store = memoryStore()
    render(<RemotePackages engine={engine()} store={store} onLoaded={vi.fn()}
      fetcher={vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))} />)
    expect(await screen.findByText(/conexión/i, { selector: '[role="alert"]' })).toBeTruthy()
    expect(store.saved).toBeNull()
  })

  it('a checksum mismatch is reported and nothing is installed', async () => {
    const store = memoryStore()
    render(<RemotePackages engine={engine()} store={store} onLoaded={vi.fn()} fetcher={await fetcher({ sha: 'deadbeef' })} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: PASS } })
    download()
    expect(await screen.findByText(/no coincide/i, { selector: '[role="alert"]' })).toBeTruthy()
    expect(store.saved).toBeNull()
  })

  it('says when no packages are published', async () => {
    const f = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) })
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={f} />)
    expect(await screen.findByText(/no hay paquetes publicados/i)).toBeTruthy()
  })
})
