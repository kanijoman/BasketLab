/**
 * The photo of a player, round, with his initials when there is none or it does not load (#1010). The photos come from a cross-origin CDN that html2canvas cannot paint, so — as in the lineups —
 * the photo is hidden in the export and an initials chip, shown only there, takes its place (`lib/exportDom`).
 */
import { useState } from 'react'
import { EXPORT_HIDE_ATTR, EXPORT_ONLY_ATTR } from '@/lib/exportDom'
import { initialsOf } from '@/lib/playerPhoto'

interface Props {
  name: string
  /** The address of the photo; ``null`` when there is none (only the initials) */
  src: string | null
  /** Side in px (default 40) */
  size?: number
}

export default function PlayerPhoto({ name, src, size = 40 }: Props) {
  const [failed, setFailed] = useState(false)
  const box = { width: size, height: size }
  const initials = (extra: Record<string, string> = {}, hidden = false) => (
    <span {...extra} aria-hidden={hidden || undefined} style={{ ...box, fontSize: Math.max(10, size * 0.38), ...(hidden ? { display: 'none' } : {}) }}
      className="inline-flex shrink-0 items-center justify-center rounded-full border-2 border-line bg-surface-raised font-semibold text-ink-muted">
      {initialsOf(name)}
    </span>
  )
  if (!src || failed) return initials()
  return (
    <>
      <span {...{ [EXPORT_HIDE_ATTR]: '' }} style={box} className="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-line">
        <img src={src} alt={name} loading="lazy" className="h-full w-full object-cover" onError={() => setFailed(true)} />
      </span>
      {initials({ [EXPORT_ONLY_ATTR]: '' }, true)}
    </>
  )
}
