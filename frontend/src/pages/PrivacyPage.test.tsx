/// <reference types="node" />
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from '@/App'
import PrivacyPage from './PrivacyPage'

// Issue #834: Google Play asks for a public privacy policy even if the app is only for the staff. Its address is part of the store listing (changing it means touching the listing),
// so it is a page of the web with a stable route, `/privacidad`. It says what the app does, and a guard keeps it from drifting from the code.
const APP = join(__dirname, '..', '..', '..', 'apps', 'live-android')

const page = () => render(<MemoryRouter><PrivacyPage /></MemoryRouter>)

/** Every source file of the app that is not a test. */
function sources(dir = join(APP, 'src')): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return sources(path)
    return /\.(ts|tsx)$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [path] : []
  })
}

describe('privacy policy (issue #834)', () => {
  it('is a page with its only h1 and a section for each thing a person wants to know', () => {
    page()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByRole('heading', { level: 1, name: /política de privacidad/i })).toBeTruthy()
    for (const name of [/qué datos/i, /en tu dispositivo/i, /con quién se comunica/i, /permisos/i, /anuncios y seguimiento/i, /contacto/i]) {
      expect(screen.getByRole('heading', { level: 2, name: name })).toBeTruthy()
    }
  })

  it('says the three things Play asks about: no ads or tracking, no accounts, and the data stays on the device', () => {
    page()
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/no tiene anuncios/i)
    expect(text).toMatch(/no hay cuentas|sin cuentas|no tiene cuentas/i)
    expect(text).toMatch(/no se envía/i)
  })

  it('names every host the app talks to (the list cannot drift from the code)', () => {
    page()
    const text = document.body.textContent ?? ''
    const hosts = new Set<string>()
    for (const file of sources()) {
      for (const match of readFileSync(file, 'utf8').matchAll(/https?:\/\/([a-z0-9.-]+\.[a-z]{2,})/gi)) hosts.add(match[1].toLowerCase())
    }
    const used = [...hosts].filter(host => !['w3.org', 'example.com', 'x'].includes(host) && !host.endsWith('.test'))
    expect(used.length).toBeGreaterThan(4)                         // the scan found the real ones
    const unlisted = used.filter(host => !text.toLowerCase().includes(host))
    expect(unlisted).toEqual([])
  })

  it('mentions the permissions that its plugins ask for (reminders and the screen kept on)', () => {
    page()
    const dependencies = Object.keys(JSON.parse(readFileSync(join(APP, 'package.json'), 'utf8')).dependencies)
    const text = document.body.textContent ?? ''
    if (dependencies.includes('@capacitor/local-notifications')) expect(text).toMatch(/notificaciones/i)
    if (dependencies.includes('@capacitor-community/keep-awake')) expect(text).toMatch(/pantalla encendida/i)
  })

  it('has a way to get in touch that is a link, and says what is kept per device', () => {
    page()
    const contact = within(screen.getByRole('heading', { level: 2, name: /contacto/i }).closest('section') as HTMLElement)
    expect(contact.getByRole('link').getAttribute('href')).toMatch(/^https:\/\//)
    expect(screen.getByText(/valoración de las alertas/i)).toBeTruthy()
  })

  it('is served at /privacidad, not taken for a competition called «privacidad»', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={['/privacidad']}><App /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByRole('heading', { level: 1, name: /política de privacidad/i })).toBeTruthy()
  })
})
