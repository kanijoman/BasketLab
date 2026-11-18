import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SourceFreshnessNotice from './SourceFreshnessNotice'
import * as client from '@/webdata/client'

// The discreet notice of a stale external source (#884, PR C), under the header, on the pages of an external competition only. The freshness is the one of `web-data-ext`: NCAA failed on its last run.
const FAILED = { source: 'ncaa', state: 'failed', ok: false, last_ok: '2026-11-17T07:00:00Z', finished: '2026-11-18T07:00:00Z', games: 13, unreliable: 12, published: 1 } as const
const NOW = Date.parse('2026-11-18T12:00:00Z')

function page(path: string) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path="/:collection/*" element={<SourceFreshnessNotice now={NOW} />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>)
}

beforeEach(() => { vi.spyOn(client, 'loadSourceFreshness').mockResolvedValue([FAILED]) })
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('the notice of a stale external source', () => {
  it('shows the date of the data on an external competition whose source failed', async () => {
    page('/NCAA_D1_2026_SEC/teams')
    expect(await screen.findByRole('status')).toHaveTextContent('Datos de NCAA del 17/11: la última actualización falló.')
  })

  it('shows nothing on a competition of FEB or FBCYL, and does not even ask for the freshness', async () => {
    page('/L_F_-2_2025_2026_Liga_Regular_B/teams')
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(screen.queryByRole('status')).toBeNull()
    expect(client.loadSourceFreshness).not.toHaveBeenCalled()
  })

  it('shows nothing for a source that is fine', async () => {
    vi.spyOn(client, 'loadSourceFreshness').mockResolvedValue([{ ...FAILED, state: 'ok', ok: true, last_ok: '2026-11-18T07:00:00Z' }])
    page('/NCAA_D1_2026_SEC/teams')
    await waitFor(() => expect(client.loadSourceFreshness).toHaveBeenCalled())
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('shows nothing, and breaks nothing, when the freshness cannot be had', async () => {
    vi.spyOn(client, 'loadSourceFreshness').mockRejectedValue(new Error('down'))
    page('/NCAA_D1_2026_SEC/teams')
    await waitFor(() => expect(client.loadSourceFreshness).toHaveBeenCalled())
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('reads the competition of an address with accents and encoded characters', async () => {
    vi.spyOn(client, 'loadSourceFreshness').mockResolvedValue([{ ...FAILED, source: 'fiba' }])
    page('/FIBA_U18_Eurobasket_Femenino_%C3%9Anico_2026_/teams')
    expect(await screen.findByRole('status')).toHaveTextContent('FIBA')
  })
})
