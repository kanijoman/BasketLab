import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const published = vi.hoisted(() => ({ publishedSectionsOf: vi.fn() }))
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), ...published }))

import RequirePublished from './RequirePublished'

// Issue #780: with the section published the page opens. #1100: the address of a page the competition cannot offer says so (the origin of the data does not bring it) instead of going away without a word.
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

  it('says the page is not available for the competition, with a way back to its summary, when it has not (#1100)', async () => {
    published.publishedSectionsOf.mockResolvedValue(new Set(['rows']))
    at('/LF2/conexiones')
    expect(await screen.findByRole('heading', { name: /no disponible para esta competición/i })).toBeInTheDocument()
    expect(screen.getByText(/el origen de los datos no lo trae o todavía no está publicado/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /volver al resumen/i })).toHaveAttribute('href', '/LF2')
    expect(screen.queryByText('Página')).toBeNull()
  })

  it('shows neither the page nor the summary while it is still finding out', async () => {
    published.publishedSectionsOf.mockReturnValue(new Promise(() => undefined))
    at('/LF2/conexiones')
    await waitFor(() => expect(published.publishedSectionsOf).toHaveBeenCalled())
    expect(screen.queryByText('Página')).toBeNull()
    expect(screen.queryByRole('heading', { name: /no disponible/i })).toBeNull()
  })

  it('with the API as the source the page opens at once', async () => {
    localStorage.setItem('basketlab.data', 'api')
    at('/LF2/conexiones')
    expect(await screen.findByText('Página')).toBeInTheDocument()
    expect(published.publishedSectionsOf).not.toHaveBeenCalled()
  })
})
