/** A team crest: the copy bundled in the app, then FEB's, then the initials (never a broken image). */
import { useState } from 'react'
import type { TeamRef } from '../engine/types'
import { initials } from './teams'

export const bundledLogo = (id: string) => `./logos/${id}.png`
export const febLogo = (id: string) => `https://imagenes.feb.es/imagen.aspx?i=${id}&ti=1`

interface Props {
  team: TeamRef
  size?: number
}

export default function TeamLogo({ team, size = 40 }: Props) {
  // 0 = bundled copy (works offline), 1 = FEB, 2 = no image: initials
  const [stage, setStage] = useState(0)
  if (stage >= 2) {
    return (
      <span className="team-logo team-logo-initials" role="presentation" aria-label={team.name}
        style={{ width: size, height: size, fontSize: Math.round(size * 0.38) }}>
        {initials(team.name)}
      </span>
    )
  }
  return (
    <img className="team-logo" src={stage === 0 ? bundledLogo(team.id) : febLogo(team.id)} alt={team.name}
      width={size} height={size} loading="lazy" onError={() => setStage(s => s + 1)} />
  )
}
