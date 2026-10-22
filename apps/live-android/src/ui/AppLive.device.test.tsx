// Live mode on a real tablet (issues #219, #220): the screen stays on while connected, and the loop polls again at once
// when the app comes back to the foreground or the network is back.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { fakeEngine, loadDemo } from './appTestKit'
import { FakeFeb, type Pack } from '../feed/fakeFeb'
import type { Device, ResumeReason } from '../feed/device'
import type { PackageStore } from '../package/storage'
import { readSession } from './sessionLog'

const PKG = JSON.stringify({
  checksum: 'x',
  package: {
    team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' }, season: '2025-2026',
    collection: 'c', created_at: '2026-10-08T12:00:00Z', tables: { players: {}, rival_players: {} },
    baselines: { sample_games: { own: 5, rival: 4, league: 50 } },
    competition_meta: { match: { code: '2524475' } },
  },
})
const store: PackageStore = { load: async () => ({ plaintext: PKG, savedAt: '2026-10-09T10:00:00Z' }), save: async () => undefined, clear: async () => undefined }
const pack: Pack = {
  v: 1, match: '2524475',
  base: { HEADER: { TEAM: [{ id: '1', pts: '0' }, { id: '2', pts: '0' }] }, BOXSCORE: { TEAM: [] }, PLAYBYPLAY: {}, SHOTCHART: {} },
  lines: [{ f: 0, l: { num: '1' } }], shots: [],
  frames: [{ t: 0, h: { status: '2', statusText: 'EN DIRECTO', quarter: 1, time: '09:50', pts: { '1': 0, '2': 0 } } }],
  gaps: {},
}

function fakeDevice(supported = true) {
  let resume: ((reason: ResumeReason) => void) | null = null
  const device: Device = {
    keepAwake: vi.fn(async () => supported), allowSleep: vi.fn(async () => undefined),
    onResume: vi.fn(cb => { resume = cb; return () => { resume = null } }),
  }
  return { device, fire: (reason: ResumeReason) => resume?.(reason), listening: () => resume !== null }
}

// a sleep that never ends by itself: only a poke can bring the next round
const longSleep = { intervalMs: 60_000, waitingIntervalMs: 60_000, tailPolls: 0, sleep: () => new Promise<void>(() => undefined) }

async function connect(supported = true) {
  const feb = new FakeFeb(pack)
  feb.at = 0
  const engine = fakeEngine()
  const dev = fakeDevice(supported)
  render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={store} febHttp={feb.get} feedTiming={longSleep} device={dev.device} />)
  fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
  await waitFor(() => expect(engine.update).toHaveBeenCalledTimes(1))
  return { engine, dev, feb }
}

describe('screen on while connected (issue #219)', () => {
  it('asks to keep the screen on when it connects and lets it sleep when it disconnects, saying so on screen', async () => {
    const { dev } = await connect()
    expect(dev.device.keepAwake).toHaveBeenCalledTimes(1)
    expect(await screen.findByText(/pantalla encendida mientras dure la conexión/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /desconectar/i }))
    await waitFor(() => expect(dev.device.allowSleep).toHaveBeenCalled())
    expect(screen.queryByText(/pantalla encendida mientras dure la conexión/i)).toBeNull()
  })

  it('does not promise it when the device cannot keep the screen on, and tells the staff', async () => {
    await connect(false)
    expect(await screen.findByText(/no se pudo mantener la pantalla encendida/i)).toBeTruthy()
    expect(screen.queryByText(/pantalla encendida mientras dure la conexión/i)).toBeNull()
  })

  it('releases the screen when the app is closed while connected', async () => {
    const { dev } = await connect()
    cleanup()
    await waitFor(() => expect(dev.device.allowSleep).toHaveBeenCalled())
  })
})

describe('reconnecting after the app was suspended or the network was lost (issue #220)', () => {
  it('polls again at once when the app returns to the foreground, and logs it', async () => {
    const { engine, dev } = await connect()
    dev.fire('foreground')
    await waitFor(() => expect(engine.update).toHaveBeenCalledTimes(2))
    expect(readSession().some(e => /vuelve a primer plano/i.test(e.text))).toBe(true)
  })

  it('polls again at once when the network is back', async () => {
    const { engine, dev } = await connect()
    dev.fire('network')
    await waitFor(() => expect(engine.update).toHaveBeenCalledTimes(2))
    expect(readSession().some(e => /red recuperada/i.test(e.text))).toBe(true)
  })

  it('does not listen when there is no connection, and stops listening when it disconnects', async () => {
    const { dev } = await connect()
    expect(dev.listening()).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: /desconectar/i }))
    await waitFor(() => expect(dev.listening()).toBe(false))
  })
})
