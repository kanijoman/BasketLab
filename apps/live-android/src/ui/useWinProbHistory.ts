/** The win probability along the match, for the card's chart (issue #257): one point per new game-second with a figure.
 *  A new match (no output) or a jump back in the timeline starts it again. */
import { useEffect, useState } from 'react'
import type { EngineOutput } from '../engine/types'

export interface WinProbPoint {
  t: number
  p: number
}

export function useWinProbHistory(out: EngineOutput | null): WinProbPoint[] {
  const [points, setPoints] = useState<WinProbPoint[]>([])
  useEffect(() => {
    if (!out) {
      setPoints(prev => (prev.length ? [] : prev))
      return
    }
    const wp = out.analysis?.win_prob
    if (!wp) return
    const t = out.snapshot.elapsed
    setPoints(prev => {
      const last = prev[prev.length - 1]
      if (last && t === last.t) return prev
      if (last && t < last.t) return [{ t, p: wp.p }]
      return [...prev, { t, p: wp.p }]
    })
  }, [out])
  return points
}
