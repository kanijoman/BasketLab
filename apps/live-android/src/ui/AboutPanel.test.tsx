import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AboutPanel, { UpdateBanner, VersionFooter, buildDiagnostics, RELEASES_URL } from './AboutPanel'
import type { AppVersion } from '../about/appInfo'
import type { LatestInfo, UpdateResult } from '../about/update'

const VERSION: AppVersion = { name: '0.2.0', build: 40, builtAt: '2026-10-13T08:20:00Z', native: true }
const LATEST: LatestInfo = { version: '0.3.0', versionCode: 52, apk: 'https://example.test/basketlab-live.apk', notes: 'Alineación indebida', builtAt: null }

afterEach(() => vi.unstubAllGlobals())

const panel = (over: Partial<Parameters<typeof AboutPanel>[0]> = {}) => {
  const props = {
    version: VERSION, update: { status: 'up_to_date', latest: LATEST } as UpdateResult, checking: false,
    onCheck: vi.fn(), onOpen: vi.fn(), diagnostics: 'DIAGNOSTICO', ...over,
  }
  render(<AboutPanel {...props} />)
  return props
}

describe('AboutPanel (issues #226 and #227)', () => {
  it('shows the app name, version and build', () => {
    panel()
    expect(screen.getByText(/BasketLab Live 0\.2\.0/)).toBeTruthy()
    expect(screen.getByText(/build 40/)).toBeTruthy()
  })

  it('a development build says so instead of inventing numbers', () => {
    panel({ version: { name: 'dev', build: null, builtAt: null, native: false }, update: { status: 'unsupported' } })
    expect(screen.getByText(/versión de desarrollo/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /buscar actualización/i })).toBeNull()
  })

  it('the button looks for an update on demand', () => {
    const p = panel()
    fireEvent.click(screen.getByRole('button', { name: /buscar actualización/i }))
    expect(p.onCheck).toHaveBeenCalledTimes(1)
  })

  it('says it is up to date, that it is checking, or that it could not tell', () => {
    const { unmount } = render(<AboutPanel version={VERSION} update={{ status: 'up_to_date', latest: LATEST }} checking={false} onCheck={() => undefined} onOpen={() => undefined} diagnostics="" />)
    expect(screen.getByText(/tienes la última versión/i)).toBeTruthy()
    unmount()
    render(<AboutPanel version={VERSION} update={{ status: 'unknown' }} checking={false} onCheck={() => undefined} onOpen={() => undefined} diagnostics="" />)
    expect(screen.getByText(/no se pudo comprobar/i)).toBeTruthy()
  })

  it('shows the new version with its notes and opens the APK when asked', () => {
    const p = panel({ update: { status: 'available', latest: LATEST } })
    expect(screen.getByText(/hay una versión nueva: 0\.3\.0/i)).toBeTruthy()
    expect(screen.getByText(/alineación indebida/i)).toBeTruthy()
    expect(screen.getByText(/android pedirá confirmación/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /descargar e instalar/i }))
    expect(p.onOpen).toHaveBeenCalledWith(LATEST.apk)
  })

  it('while checking the button is disabled', () => {
    panel({ checking: true })
    expect((screen.getByRole('button', { name: /buscando/i }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows the engine and the package schema versions when known', () => {
    panel({ engineVersion: 'ab12cd34', schemaVersion: 1 })
    expect(screen.getByText(/motor ab12cd34/i)).toBeTruthy()
    expect(screen.getByText(/esquema de paquete 1/i)).toBeTruthy()
  })

  it('opens the release notes and has no link to the repository (#408)', () => {
    const p = panel()
    expect(screen.queryByRole('button', { name: /repositorio/i })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /notas de la versión/i }))
    expect(p.onOpen).toHaveBeenCalledWith(RELEASES_URL)
  })

  it('copies the diagnostics for an issue', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    panel()
    fireEvent.click(screen.getByRole('button', { name: /copiar diagnóstico/i }))
    await waitFor(() => expect(screen.getByText('Copiado')).toBeTruthy())
    expect(writeText).toHaveBeenCalledWith('DIAGNOSTICO')
  })

  it('says so when the clipboard is not available', async () => {
    vi.stubGlobal('navigator', {})
    panel()
    fireEvent.click(screen.getByRole('button', { name: /copiar diagnóstico/i }))
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/no se pudo copiar/i))
  })
})

describe('UpdateBanner', () => {
  it('is a discreet notice with the way to update', () => {
    const onOpen = vi.fn()
    render(<UpdateBanner latest={LATEST} onOpen={onOpen} />)
    expect(screen.getByRole('status').textContent).toMatch(/versión nueva: 0\.3\.0/i)
    fireEvent.click(screen.getByRole('button', { name: /actualizar/i }))
    expect(onOpen).toHaveBeenCalledWith(LATEST.apk)
  })
})

describe('VersionFooter', () => {
  it('shows app and engine versions in one discreet line', () => {
    render(<VersionFooter version={VERSION} engineVersion="ab12cd34" />)
    expect(screen.getByText(/BasketLab Live 0\.2\.0/).textContent).toMatch(/motor ab12cd34/)
  })

  it('leaves the engine out until it is known', () => {
    render(<VersionFooter version={VERSION} engineVersion={null} />)
    expect(screen.getByText(/BasketLab Live 0\.2\.0/).textContent).not.toMatch(/motor/)
  })
})

describe('buildDiagnostics', () => {
  it('has what is needed to report a problem and nothing secret', () => {
    const text = buildDiagnostics({ version: VERSION, userAgent: 'UA/1.0', packageId: 'FEB:1:2026', schemaVersion: 1, feed: 'live' })
    expect(text).toContain('BasketLab Live 0.2.0 (build 40)')
    expect(text).toContain('UA/1.0')
    expect(text).toContain('FEB:1:2026')
    expect(text).toContain('esquema de paquete 1')
    expect(text).toContain('live')
  })

  it('includes the engine version', () => {
    const text = buildDiagnostics({ version: VERSION, userAgent: 'UA', packageId: null, schemaVersion: null, feed: null, engineVersion: 'ab12cd34' })
    expect(text).toContain('Motor: ab12cd34')
  })

  it('copes with nothing loaded yet', () => {
    const text = buildDiagnostics({ version: null, userAgent: 'UA', packageId: null, schemaVersion: null, feed: null })
    expect(text).toContain('sin paquete')
  })
})

describe('session log in the About panel (issue #309)', () => {
  it('shows the recent events with their time', () => {
    panel({ sessionLog: ['14/10 16:05:12 · Arranque de la app', '14/10 16:06:40 · Partido reiniciado con el botón Reiniciar'] })
    const block = screen.getByRole('region', { name: 'Registro de la sesión' })
    expect(block.textContent).toMatch(/Arranque de la app/)
    expect(block.textContent).toMatch(/Partido reiniciado/)
  })

  it('without events it says there are none', () => {
    panel({ sessionLog: [] })
    expect(screen.getByText(/sin eventos todavía/i)).toBeTruthy()
  })

  it('the diagnostics carry the latest events', () => {
    const text = buildDiagnostics({ version: VERSION, userAgent: 'UA', packageId: null, schemaVersion: null, feed: null, sessionLog: ['a', 'b'] })
    expect(text).toContain('Registro reciente')
    expect(text).toContain('- a')
    expect(text).toContain('- b')
  })
})
