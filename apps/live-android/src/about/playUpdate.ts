/**
 * The update notice of the build for Google Play (issue #1043). Play installs the app, but it never told the staff a newer version was there. This asks Play
 * through its in-app update API (a FLEXIBLE update: it downloads in the background and the app says «restart to install») and, when Play does not offer
 * what the release channel already published (`latest.json`), says so with a way to reach it.
 *
 * Nothing here runs in the APK build or in a browser: `resolvePlayUpdate` answers «unsupported» before it even creates the updater, and the plugin is
 * loaded on demand (and compiled out of every build but the Play one).
 */
import type { AppUpdatePlugin } from '@capawesome/capacitor-app-update'
import type { AppVersion } from './appInfo'
import { isNewer, type LatestInfo } from './update'

export type PlayAvailability = 'unknown' | 'none' | 'available' | 'in_progress'
export type PlayInstall = 'unknown' | 'pending' | 'downloading' | 'downloaded' | 'installing' | 'installed' | 'failed' | 'canceled'

export interface PlayInfo {
  availability: PlayAvailability
  installStatus: PlayInstall
  /** The build number Play offers, when it offers one. */
  availableCode: number | null
  /** Play lets the update be downloaded without leaving the app. */
  flexibleAllowed: boolean
}

export type PlayStart = 'ok' | 'canceled' | 'failed' | 'not_available' | 'not_allowed'

/** What the app needs from Play (the plugin behind it; tests inject a fake). */
export interface PlayUpdater {
  getInfo(): Promise<PlayInfo>
  /** Asks Play to download the update in the background (the system asks the user to confirm it). */
  startFlexible(): Promise<PlayStart>
  /** Installs what was downloaded: the app restarts. */
  complete(): Promise<void>
  /** Progress of the download; returns the function that stops listening. */
  onStatus(callback: (status: { install: PlayInstall; percent: number | null }) => void): Promise<() => void>
}

export type PlayUpdateState =
  | { status: 'unsupported' }                                       // not the Play build, or not the Android app
  | { status: 'unknown' }                                           // Play did not answer
  | { status: 'up_to_date' }
  | { status: 'available'; versionCode: number | null }
  | { status: 'downloading'; percent: number | null }
  | { status: 'downloaded' }
  | { status: 'not_offered'; latest: LatestInfo }                   // published, but Play does not offer it to this tablet
  | { status: 'error'; reason: 'failed' | 'not_allowed' }

export interface ResolveDeps {
  installed: AppVersion | null
  /** Created only for the Play build. */
  updater: () => PlayUpdater
  /** The published release description (`latest.json`), or null when it cannot be had. */
  latest: () => Promise<LatestInfo | null>
}

export async function resolvePlayUpdate(d: ResolveDeps): Promise<PlayUpdateState> {
  if (!d.installed || !d.installed.native || d.installed.distribution !== 'play') return { status: 'unsupported' }
  let info: PlayInfo
  try {
    info = await d.updater().getInfo()
  } catch {
    return { status: 'unknown' }
  }
  if (info.installStatus === 'downloaded') return { status: 'downloaded' }
  if (info.availability === 'unknown') return { status: 'unknown' }
  if (info.availability === 'in_progress') return { status: 'downloading', percent: null }
  if (info.availability === 'available') return { status: 'available', versionCode: info.availableCode }
  // Play sees nothing newer: is something published that Play does not give to this tablet?
  try {
    const latest = await d.latest()
    if (latest && isNewer(latest, d.installed)) return { status: 'not_offered', latest }
  } catch {
    /* the release channel is only a hint: without it Play's answer stands */
  }
  return { status: 'up_to_date' }
}

export interface PlayText {
  text: string | null
  /** The label of the button, when there is something to press. */
  action: 'Descargar' | 'Reiniciar e instalar' | 'Reintentar' | null
}

/** The sentence for each state, in Spanish. The «not offered» one says how to reach the update while the store listing is not reviewed (#1043: temporary name, testers link). */
export function playUpdateText(state: PlayUpdateState): PlayText {
  switch (state.status) {
    case 'unsupported': return { text: null, action: null }
    case 'up_to_date': return { text: 'Tienes la última versión.', action: null }
    case 'unknown': return { text: 'No se pudo consultar Google Play (¿sin conexión?).', action: null }
    case 'available': return { text: 'Hay una versión nueva en Google Play.', action: 'Descargar' }
    case 'downloading': return { text: state.percent === null ? 'Descargando la versión nueva…' : `Descargando la versión nueva… ${state.percent} %`, action: null }
    case 'downloaded': return { text: 'Versión nueva descargada. Reinicia la app para instalarla.', action: 'Reiniciar e instalar' }
    case 'error':
      return state.reason === 'not_allowed'
        ? { text: 'Google Play no permite actualizar sin salir de la app: actualiza desde la ficha de la tienda.', action: null }
        : { text: 'Google Play no ha podido descargar la versión nueva.', action: 'Reintentar' }
    case 'not_offered':
      return {
        text: `La versión ${state.latest.version} ya está publicada, pero Google Play no se la ofrece a esta tablet todavía. Ábrela desde el enlace de pruebas internas o búscala en Google Play como «es.basketlab.live (unreviewed)»; si no aparece, avisa a quien administra Play.`,
        action: null,
      }
  }
}

const AVAILABILITY: Record<number, PlayAvailability> = { 0: 'unknown', 1: 'none', 2: 'available', 3: 'in_progress' }
const INSTALL: Record<number, PlayInstall> = { 0: 'unknown', 1: 'pending', 2: 'downloading', 3: 'installing', 4: 'installed', 5: 'failed', 6: 'canceled', 11: 'downloaded' }
const START: Record<number, PlayStart> = { 0: 'ok', 1: 'canceled', 2: 'failed', 3: 'not_available', 4: 'not_allowed', 5: 'failed' }

/** The plugin, loaded when something asks for it; the import is compiled out of every build but the one for Google Play. */
export const loadPlugin = (): Promise<AppUpdatePlugin> =>
  import.meta.env.VITE_DISTRIBUTION === 'play'
    ? import('@capawesome/capacitor-app-update').then(m => m.AppUpdate)
    : Promise.reject(new Error('The update plugin of Google Play is only in the Play build'))

/** The updater of the app over the plugin of Play. ``load`` is injected in tests. */
export function createNativeUpdater(load: () => Promise<AppUpdatePlugin> = loadPlugin): PlayUpdater {
  let plugin: Promise<AppUpdatePlugin> | null = null
  const get = () => (plugin ??= load())
  return {
    async getInfo() {
      const raw = await (await get()).getAppUpdateInfo()
      const code = Number(raw.availableVersionCode)
      return {
        availability: AVAILABILITY[raw.updateAvailability] ?? 'unknown', installStatus: INSTALL[raw.installStatus ?? 0] ?? 'unknown',
        availableCode: Number.isInteger(code) && code > 0 ? code : null, flexibleAllowed: raw.flexibleUpdateAllowed === true,
      }
    },
    async startFlexible() {
      return START[(await (await get()).startFlexibleUpdate()).code] ?? 'failed'
    },
    async complete() {
      await (await get()).completeFlexibleUpdate()
    },
    async onStatus(callback) {
      const handle = await (await get()).addListener('onFlexibleUpdateStateChange', state => {
        const install = INSTALL[state.installStatus] ?? 'unknown'
        const known = state.totalBytesToDownload && state.bytesDownloaded !== undefined
        callback({ install, percent: install === 'downloaded' ? 100 : known ? Math.round((100 * state.bytesDownloaded!) / state.totalBytesToDownload!) : null })
      })
      return () => { void handle.remove() }
    },
  }
}
