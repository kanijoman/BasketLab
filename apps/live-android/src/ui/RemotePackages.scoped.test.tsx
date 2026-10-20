// Packages sealed by scope (issue #410): the beta opens without a password, an invitation opens the rest, a password one keeps working.
import { webcrypto } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RemotePackages from './RemotePackages'
import type { PackageStore, StoredPackage } from '../package/storage'
import type { EngineApi } from '../engine/client'

const repoRoot = path.resolve(import.meta.dirname, '../../../..')
const demo = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo_scoped.json'), 'utf8'))
const demoPackage: string = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/vectors.json'), 'utf8')).engine.package
const RIGHTS_KEY = 'basketlab-live-rights'

async function sha(text: string) {
  const buf = await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, '0')).join('')
}

function memoryStore(): PackageStore & { saved: StoredPackage | null } {
  const s = { saved: null as StoredPackage | null, load: async () => s.saved, save: async (r: StoredPackage) => { s.saved = r }, clear: async () => { s.saved = null } }
  return s
}
const META = { team: { id: '1', name: 'A' }, rival: { id: '2', name: 'B' } }
const engine = () => ({ start: vi.fn().mockResolvedValue(META) }) as unknown as EngineApi

/** A scoped index: ``open`` publishes the key of the open scope (the beta), without it only an invitation opens the package. */
async function fetcher(options: { open: boolean }) {
  const index = {
    v: 2, generated_at: '2026-11-07T11:42:25+00:00', ...(options.open ? { open_key: demo.open_key } : {}),
    packages: [{
      team_id: '1008631', rival_id: '1008898', rival: 'RECOLETAS ZAMORA', file: '1008631/1008898.bpkg', sha256: await sha(demo.package.file), bytes: 100,
      wraps: demo.package.wraps,
      match: { code: '2524470', start: '2026-10-10T17:00', round: 2, home: { id: '1008898', name: 'RECOLETAS ZAMORA' }, away: { id: '1008631', name: 'LEON' } },
    }],
    rounds: [],
  }
  return vi.fn(async (url: string) => {
    const body = url.endsWith('index.json') ? JSON.stringify(index) : demo.package.file
    return { ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) }
  })
}

const download = () => fireEvent.click(screen.getByRole('button', { name: /^descargar$/i }))

beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto)
  localStorage.clear()
})

describe('RemotePackages with the open scope (the beta)', () => {
  it('asks for no password and downloads with the key published in the index', async () => {
    const store = memoryStore()
    const onLoaded = vi.fn()
    render(<RemotePackages engine={engine()} store={store} onLoaded={onLoaded} fetcher={await fetcher({ open: true })} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    expect(screen.queryByLabelText(/contraseña/i)).toBeNull()
    expect(screen.queryByLabelText(/invitación/i)).toBeNull()
    expect(screen.getByText(/acceso abierto/i)).toBeTruthy()
    download()
    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
    expect(store.saved?.plaintext).toBe(demoPackage)
  })
})

describe('RemotePackages when the key is on (issue #410)', () => {
  it('without a right the match cannot be downloaded and the screen says what to do', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher({ open: false })} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    expect((screen.getByRole('button', { name: /^descargar$/i }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/sin acceso/i)).toBeTruthy()
    expect(screen.getByLabelText(/invitación/i)).toBeTruthy()
  })

  it('an invitation pasted as a link gives the right, is remembered and opens the download', async () => {
    const store = memoryStore()
    const onLoaded = vi.fn()
    render(<RemotePackages engine={engine()} store={store} onLoaded={onLoaded} fetcher={await fetcher({ open: false })} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    fireEvent.change(screen.getByLabelText(/invitación/i), { target: { value: ` ${demo.invitations['club:1008631'].link}\n` } })
    fireEvent.click(screen.getByRole('button', { name: /usar invitación/i }))
    expect(await screen.findByText(/club:1008631/)).toBeTruthy()
    expect(JSON.parse(localStorage.getItem(RIGHTS_KEY) ?? '[]')[0].scope).toBe('club:1008631')
    download()
    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
    expect(store.saved?.plaintext).toBe(demoPackage)
  })

  it('the right of a previous session is used from the start', async () => {
    const token = demo.invitations['club:1008631'].token
    const { parseInvite } = await import('../package/rights')
    localStorage.setItem(RIGHTS_KEY, JSON.stringify([parseInvite(token)]))
    const onLoaded = vi.fn()
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={onLoaded} fetcher={await fetcher({ open: false })} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    download()
    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
  })

  it('an invitation to another scope is kept but does not open this match', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher({ open: false })} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    fireEvent.change(screen.getByLabelText(/invitación/i), { target: { value: demo.invitations['club:999'].token } })
    fireEvent.click(screen.getByRole('button', { name: /usar invitación/i }))
    await screen.findByText(/club:999/)
    expect((screen.getByRole('button', { name: /^descargar$/i }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('something that is not an invitation is refused with a message and nothing is kept', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher({ open: false })} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    fireEvent.change(screen.getByLabelText(/invitación/i), { target: { value: 'hola' } })
    fireEvent.click(screen.getByRole('button', { name: /usar invitación/i }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/no es una invitación/i)
    expect(localStorage.getItem(RIGHTS_KEY)).toBeNull()
  })
})
