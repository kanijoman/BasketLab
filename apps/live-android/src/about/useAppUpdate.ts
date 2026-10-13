import { Browser } from '@capacitor/browser'
import { useCallback, useEffect, useRef, useState } from 'react'
import { getInstalledVersion, type AppVersion } from './appInfo'
import { checkForUpdate, fetchJson, type StorageLike, type UpdateResult } from './update'

/** Everything the update check touches from the outside (injected in tests). */
export interface AppUpdateDeps {
  getInstalled: () => Promise<AppVersion>
  fetchJson: (url: string) => Promise<unknown>
  /** Opens the APK link; the system then asks the user to confirm the installation. */
  openUrl: (url: string) => void | Promise<unknown>
  storage?: StorageLike | null
  now?: () => number
}

export const DEFAULT_UPDATE_DEPS: AppUpdateDeps = {
  getInstalled: () => getInstalledVersion(),
  fetchJson,
  openUrl: url => Browser.open({ url }),
  storage: (() => { try { return typeof localStorage === 'undefined' ? null : localStorage } catch { return null } })(),
}

/** Installed version, the last answer about a newer one, and the ways to check again and to open the APK. */
export function useAppUpdate(deps: AppUpdateDeps = DEFAULT_UPDATE_DEPS) {
  const depsRef = useRef(deps)
  const [installed, setInstalled] = useState<AppVersion | null>(null)
  const [result, setResult] = useState<UpdateResult | null>(null)
  const [checking, setChecking] = useState(false)

  const check = useCallback(async (version: AppVersion, force: boolean) => {
    const d = depsRef.current
    setChecking(true)
    try {
      setResult(await checkForUpdate({ installed: version, fetchJson: d.fetchJson, storage: d.storage, now: d.now, force }))
    } finally {
      setChecking(false)
    }
  }, [])

  // on opening: the installed version and, inside the app, a (cached) look at what is published
  useEffect(() => {
    let alive = true
    void (async () => {
      const version = await depsRef.current.getInstalled()
      if (!alive) return
      setInstalled(version)
      await check(version, false)
    })()
    return () => { alive = false }
  }, [check])

  const checkNow = useCallback(() => { if (installed) void check(installed, true) }, [installed, check])
  const open = useCallback((url: string) => { void Promise.resolve(depsRef.current.openUrl(url)).catch(() => undefined) }, [])
  return { installed, result, checking, checkNow, open }
}
