import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import BrandHeader from './BrandHeader'
import Splash from './Splash'
import { fakeEngine, loadDemo } from './appTestKit'

beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})
afterEach(() => vi.useRealTimers())

describe('brand of the app (issue #311)', () => {
  it('the header has the logo and the name of the app', () => {
    render(<BrandHeader />)
    const header = screen.getByRole('banner')
    expect(header.querySelector('img')).toBeTruthy()
    expect(header.textContent).toMatch(/BasketLab\s*Live/)
  })

  it('the loading screen is a splash with the logo, the name and what it is doing', () => {
    render(<Splash />)
    const splash = screen.getByRole('status')
    expect(splash.textContent).toMatch(/BasketLab\s*Live/)
    expect(splash.textContent).toMatch(/Cargando motor…/)
    expect(splash.querySelector('img')).toBeTruthy()
    expect(splash.querySelector('.splash-progress')).toBeTruthy()
  })

  it('while the engine loads the app shows the splash, and then the header on every tab', async () => {
    let release: () => void = () => undefined
    const engine = fakeEngine({ start: vi.fn(() => new Promise(resolve => { release = () => resolve({
      package_id: 'p', schema_version: 1, created_at: '', collection: 'c', season: '2025',
      team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' } }) })) as never })
    render(<App engine={engine} loadDemo={loadDemo} />)
    expect(await screen.findByText('Cargando motor…')).toBeTruthy()
    expect(document.querySelector('.splash')).toBeTruthy()
    release()
    await screen.findByText('EQUIPO PROPIO')
    expect(document.querySelector('.splash')).toBeNull()
    for (const tab of ['Partido', 'Paquetes', 'Acerca de']) {
      fireEvent.click(screen.getByRole('tab', { name: tab }))
      expect(document.querySelector('.brand-header')?.textContent).toMatch(/BasketLab\s*Live/)
    }
  })

  it('Acerca de shows the logo, the name and the version together', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('tab', { name: 'Acerca de' }))
    const about = screen.getByRole('region', { name: 'Acerca de' })
    expect(about.querySelector('img.about-logo')).toBeTruthy()
  })
})
