/** The session log for the screen (issue #309): logs the start of the app, beats while it is open and gives the latest events. */
import { useCallback, useEffect, useState } from 'react'
import { BEAT_EVERY_MS, beat, formatSession, markStartup, readSession, recordSession } from './sessionLog'

const SHOWN = 8

export function useSessionLog(): { lines: string[]; record: (text: string) => void } {
  const [lines, setLines] = useState<string[]>([])
  const refresh = useCallback(() => setLines(readSession().slice(-SHOWN).reverse().map(formatSession)), [])
  const record = useCallback((text: string) => { recordSession(text); refresh() }, [refresh])
  useEffect(() => {
    markStartup()
    refresh()
    const timer = setInterval(beat, BEAT_EVERY_MS)
    return () => clearInterval(timer)
  }, [refresh])
  return { lines, record }
}
