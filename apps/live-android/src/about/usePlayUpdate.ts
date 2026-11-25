import { useCallback, useEffect, useRef, useState } from 'react'
import { capacitorDevice } from '../feed/device'
import type { AppVersion } from './appInfo'
import { createNativeUpdater, resolvePlayUpdate, type PlayUpdater, type PlayUpdateState } from './playUpdate'
import { LATEST_URL, parseLatest } from './update'

/** What the check of Play touches from the outside (injected in tests). */
export interface PlayUpdateDeps {
  /** Created only for the Play build, when something asks for it. */
  updater: () => PlayUpdater
  now?: () => number
  /** Calls back when the app returns to the foreground; returns the function that stops listening. */
  onResume?: (callback: () => void) => () => void
}

export const DEFAULT_PLAY_DEPS: PlayUpdateDeps = {
  updater: () => createNativeUpdater(),
  onResume: callback => capacitorDevice.onResume(() => callback()),
}

// Coming back to the foreground asks Play again, but not more than once in a while (Play itself caches what it knows).
const MIN_INTERVAL_MS = 10 * 60 * 1000

/**
 * The update of the build for Google Play (issue #1043): what Play says about the installed build, and the ways to download the new one in the background and
 * to restart into it. Everything is inert in the APK build and in a browser (the state is «unsupported»: Play is never asked and the plugin is never loaded).
 */
export function usePlayUpdate(installed: AppVersion | null, fetchJson: (url: string) => Promise<unknown>, deps: PlayUpdateDeps = DEFAULT_PLAY_DEPS) {
  const depsRef = useRef(deps)
  const fetchRef = useRef(fetchJson)
  const updater = useRef<PlayUpdater | null>(null)
  const stopListening = useRef<(() => void) | null>(null)
  const lastCheck = useRef<number | null>(null)
  const [state, setState] = useState<PlayUpdateState | null>(null)
  const [checking, setChecking] = useState(false)

  const getUpdater = useCallback(() => (updater.current ??= depsRef.current.updater()), [])
  const now = () => (depsRef.current.now ?? Date.now)()

  const check = useCallback(async (version: AppVersion) => {
    setChecking(true)
    lastCheck.current = now()
    try {
      setState(await resolvePlayUpdate({
        installed: version, updater: getUpdater,
        latest: async () => parseLatest(await fetchRef.current(LATEST_URL)),
      }))
    } finally {
      setChecking(false)
    }
  }, [getUpdater])

  const supported = Boolean(installed?.native && installed.distribution === 'play')

  // on opening
  useEffect(() => {
    if (installed && supported) void check(installed)
  }, [installed, supported, check])

  // coming back to the foreground
  useEffect(() => {
    if (!installed || !supported || !depsRef.current.onResume) return
    return depsRef.current.onResume(() => {
      if (lastCheck.current === null || now() - lastCheck.current >= MIN_INTERVAL_MS) void check(installed)
    })
  }, [installed, supported, check])

  useEffect(() => () => { stopListening.current?.() }, [])

  const checkNow = useCallback(() => { if (installed && supported) void check(installed) }, [installed, supported, check])

  /** Asks Play to download the new version in the background; the user confirms in the system dialog. */
  const start = useCallback(async () => {
    const u = getUpdater()
    stopListening.current?.()
    try {
      stopListening.current = await u.onStatus(({ install, percent }) => {
        if (install === 'downloaded') { setState({ status: 'downloaded' }); stopListening.current?.(); stopListening.current = null }
        else if (install === 'failed' || install === 'canceled') setState({ status: 'error', reason: 'failed' })
        else if (install === 'downloading' || install === 'pending') setState({ status: 'downloading', percent })
      })
      const result = await u.startFlexible()
      if (result === 'ok') setState(current => (current?.status === 'downloaded' ? current : { status: 'downloading', percent: null }))
      else {
        stopListening.current?.()
        stopListening.current = null
        if (result === 'canceled') setState({ status: 'available', versionCode: null })
        else if (result === 'not_allowed') setState({ status: 'error', reason: 'not_allowed' })
        else if (result === 'not_available' && installed) await check(installed)
        else setState({ status: 'error', reason: 'failed' })
      }
    } catch {
      setState({ status: 'error', reason: 'failed' })
    }
  }, [getUpdater, check, installed])

  /** Installs what was downloaded: the app restarts. */
  const restart = useCallback(async () => {
    try { await getUpdater().complete() } catch { setState({ status: 'error', reason: 'failed' }) }
  }, [getUpdater])

  return { state, checking, checkNow, start, restart }
}
