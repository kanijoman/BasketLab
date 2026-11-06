import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const published = vi.hoisted(() => ({ publishedSectionsOf: vi.fn() }))
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), ...published }))

import RequirePublished from './RequirePublished'

// Issue #780: the address of a hidden page goes back to the competition's summary; with the section published the page opens.
const at = (path: string) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route path="/:collection">
        <Route index element={<p>Resumen</p>} />
        <Route path="conexiones" element={<RequirePublished requires={{ section: 'assist_connections', dataset: 'assist-connections' }}><p>Página</p></RequirePublished>} />
      </Route>
    </Routes>
  </MemoryRouter>)

beforeEach(() => { localStorage.clear(); published.publishedSectionsOf.mockReset() })

describe('RequirePublished', () => {
  it('opens the page when the competition has the section', async () => {
    published.publishedSectionsOf.mockResolvedValue(new Set(['assist_connections']))
    at('/LF2/conexiones')
    expect(await screen.findByText('Página')).toBeInTheDocument()
  })

  it('goes to the summary of the competition when it has not', async () => {
    published.publishedSectionsOf.mockResolvedValue(new Set(['rows']))
    at('/LF2/conexiones')
    expect(await screen.findByText('Resumen')).toBeInTheDocument()
    expect(screen.queryByText('Página')).toBeNull()
  })

  it('shows neither the page nor the summary while it is still finding out', async () => {
    published.publishedSectionsOf.mockReturnValue(new Promise(() => undefined))
    at('/LF2/conexiones')
    await waitFor(() => expect(published.publishedSectionsOf).toHaveBeenCalled())
    expect(screen.queryByText('Página')).toBeNull()
    expect(screen.queryByText('Resumen')).toBeNull()
  })

  it('with the API as the source the page opens at once', async () => {
    localStorage.setItem('basketlab.data', 'api')
    at('/LF2/conexiones')
    expect(await screen.findByText('Página')).toBeInTheDocument()
    expect(published.publishedSectionsOf).not.toHaveBeenCalled()
  })
})
