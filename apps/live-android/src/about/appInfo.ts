/**
 * The installed version of the app (issues #226 and #227). On the device it comes from the APK (`versionName` and
 * `versionCode`, through @capacitor/app); the workflow also compiles the same numbers into the web build
 * (VITE_APP_VERSION, VITE_APP_BUILD, VITE_BUILT_AT) for a browser and as a fallback. The build number is what is
 * compared with the published one: CI makes it grow with every release.
 */
import { App as CapApp } from '@capacitor/app'
import { Capacitor } from '@capacitor/core'

export interface AppVersion {
  /** versionName, e.g. «0.3.0»; «dev» when nobody said. */
  name: string
  /** versionCode (grows with every release); null when unknown, so it never looks outdated. */
  build: number | null
  builtAt: string | null
  /** True inside the Android app: only there can the app update itself. */
  native: boolean
}

interface Env {
  VITE_APP_VERSION?: string
  VITE_APP_BUILD?: string
  VITE_BUILT_AT?: string
}

export interface AppInfoDeps {
  native: () => boolean
  getInfo: () => Promise<{ build: string; version: string }>
  env: Env
}

const positiveInt = (value: unknown): number | null => {
  const n = Number(value)
  return Number.isInteger(n) && n > 0 ? n : null
}

export function buildInfo(env: Env = import.meta.env as Env): { name: string; build: number | null; builtAt: string | null } {
  return { name: env.VITE_APP_VERSION || 'dev', build: positiveInt(env.VITE_APP_BUILD), builtAt: env.VITE_BUILT_AT || null }
}

const DEFAULTS: AppInfoDeps = { native: () => Capacitor.isNativePlatform(), getInfo: () => CapApp.getInfo(), env: import.meta.env as Env }

export async function getInstalledVersion(deps: AppInfoDeps = DEFAULTS): Promise<AppVersion> {
  const compiled = buildInfo(deps.env)
  if (!deps.native()) return { ...compiled, native: false }
  try {
    const info = await deps.getInfo()
    return { name: info.version || compiled.name, build: positiveInt(info.build), builtAt: compiled.builtAt, native: true }
  } catch {
    return { ...compiled, native: true }  // the plugin failed: the numbers compiled into the web build still tell
  }
}
