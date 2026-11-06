/** Assist connections of a team (issue #773): who passes, who receives and from which zones the receiver scores, assisted against not assisted. */
import { fromSource } from '@/datasource/resolve'
import { localAssistConnections } from '@/localdata/source'
import { get } from './http'

export interface ConnectionZone {
  zone: string
  assisted: number
  unassisted: number
  /** Share of the baskets of the zone that were assisted (0-100). */
  assisted_pct: number | null
}

export interface ConnectionLink {
  player_id: string
  name: string
  count: number
}

export interface Receiver {
  player_id: string
  name: string
  /** Baskets scored with an assist. */
  received: number
  unassisted: number
  /** All the made baskets of the player (field goals). */
  fgm: number
  /** Points of those field goals, and the part of them that came from an assisted basket. */
  points: number
  assisted_points: number
  assisted_points_pct: number
  /** Share of the assisted baskets of the team that this player scored. */
  share_pct: number
  /** Share of the player's own baskets that were assisted. */
  assisted_pct: number
  zones: ConnectionZone[]
  /** Baskets whose zone is unknown (no shot coordinates). */
  without_zone: number
  from: ConnectionLink[]
}

/** A zone of the court and the assists of a passer that end in a basket scored there. */
export interface PassZone {
  zone: string
  count: number
}

/** One player a passer finds: how many assists, and the zones those baskets were scored from (``without_zone``: no shot coordinates). */
export interface PassTarget extends ConnectionLink {
  zones: PassZone[]
  without_zone: number
}

export interface Passer {
  player_id: string
  name: string
  assists: number
  share_pct: number
  to: PassTarget[]
  /** Where the baskets he created were scored from, and how many of his assists have no known zone. */
  zones: PassZone[]
  without_zone: number
}

export interface AssistConnections {
  team_id: string
  games: number
  assisted_baskets: number
  total_baskets: number
  assists_total: number
  assists_linked: number
  /** Share of the team's assists that could be tied to a basket (null without assists). */
  linked_pct: number | null
  receivers: Receiver[]
  passers: Passer[]
  focus?: { as_receiver: Receiver | null; as_passer: Passer | null }
  format?: 'feb' | 'fbcyl'
  collection?: string
}

export function getAssistConnections(collection: string, teamId: string): Promise<AssistConnections> {
  return fromSource(
    'assist-connections',
    () => localAssistConnections(collection, teamId),
    () => get<AssistConnections>(`/assist-connections/${encodeURIComponent(collection)}/${encodeURIComponent(teamId)}`),
  )
}
