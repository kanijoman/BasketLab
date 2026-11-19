// What BasketLab Talent reads (epic #872, B2 #878): the `talent-data` branch, one sealed file per competition and season with a row per player, team and competition. Same static host, same
// sealing and same unlocking as `web-data` (`@/webdata/sealedClient`), another manifest (`./contract.generated`) and another branch: the two publications are written by two workflows and
// a failure of one does not stop the other. The base is fixed here, not in an environment variable: the Vercel project of Talent needs none.
import { DataUnavailable } from '@/datasource/resolve'
import { createSealedClient } from '@/webdata/sealedClient'
import { TALENT_SCHEMA, type TalentCompetitionEntry, type TalentManifest } from './contract.generated'

export const TALENT_DEFAULT_BASE = 'https://raw.githubusercontent.com/kanijoman/BasketLab/talent-data/'

/** The data cannot be had from `talent-data`: there is no answer. */
export class TalentDataUnavailable extends DataUnavailable {}

export type { TalentCompetitionEntry, TalentManifest } from './contract.generated'

/** The profile of a player in his competition: per-40 rates and shooting, the role (z-scores of the live engine) and the percentiles among those who played enough (for `tov`, lower is better). */
export interface TalentRates { pts: number; orb: number; drb: number; ast: number; tov: number; stl: number; blk: number; fg3a: number; fg2a: number; usage: number; efg: number; ftr: number; ts: number }
export interface TalentRole { orb40: number; drb40: number; ast40: number; blk40: number; fg3a40: number; fg2a40: number; usage40: number }
export type TalentPercentiles = Record<keyof TalentRates | 'usage_pct' | 'pie', number | null>

/** A row of a competition: one player in ONE team and ONE competition (a transfer inside it is two rows). Minutes are seconds for FEB and FBCYL alike. */
export interface TalentRow {
  person_id: string
  name: string
  full_name: string | null
  team_id: string
  team_name: string
  league: 'feb' | 'fbcyl'
  groups: string[]
  games: number
  minutes: number
  pts: number; p1m: number; p1a: number; p2m: number; p2a: number; p3m: number; p3a: number
  assist: number; ro: number; rd: number; rt: number; st: number; to: number; bs: number; pf: number; rf: number; val: number; pllss: number
  usage_pct: number; orating: number; drating: number; net_rtg: number; ast_pct: number; tov_pct_adv: number
  stl_pct: number; blk_pct: number; drb_pct: number; orb_pct: number; pie: number
  birth: string | null; height: number | null; position: string | null; position_group: 'G' | 'F' | 'C' | null; nationality: string | null; formacion: boolean | null; dorsal: number | null
  /** Height, position, birth date or nationality that the roster of the row did not say and another team or season of the same person did: `{ height: '2024:10' }` (`season:team` of a FEB roster, `source:season` of an external one). */
  bio_from: Record<string, string>
  /** Every different nationality of the person, the closest season first (`nationality` is the first); a date of birth the sources disagree on is `['birth']` in `bio_conflict` (#996). */
  nationalities: string[]
  bio_conflict: string[]
  /** The FEB person (`feb:<id>`) this row IS when the identity link of its player is `linked` (#996); `person_id` is not rewritten. Only FBCYL rows say it. */
  linked_to: string | null
  eligible: boolean
  per40: TalentRates | null
  role: TalentRole | null
  pct: TalentPercentiles | null
}

export interface TalentCompetition {
  format: number
  competition: { key: string; league: 'feb' | 'fbcyl'; competition: string; season: string; season_label: string; groups: string[]; gender?: 'F' | 'M'; level?: number }
  rows: TalentRow[]
}

const talent = createSealedClient<TalentManifest>({ base: TALENT_DEFAULT_BASE, schema: TALENT_SCHEMA, unavailable: TalentDataUnavailable })

/** Where the publication is (tests, or a host other than the default). */
export const setTalentBase = talent.setBase

/** Forget what was loaded (tests, or a manifest that was replaced). */
export const resetTalentData = talent.reset

/** The competitions and seasons published, with what the manifest says of each (league, gender, level, players). */
export async function loadTalentCompetitions(): Promise<TalentCompetitionEntry[]> {
  return (await talent.loadManifest()).competitions
}

/** The rows of a competition and season, opened with the open key and the rights of the reader. */
export const loadCompetitionRows = (key: string): Promise<TalentCompetition> =>
  talent.openSealed<TalentCompetition>(async () => {
    const manifest = await talent.loadManifest()
    const entry = manifest.competitions.find(c => c.key === key)
    if (!entry) throw new TalentDataUnavailable('Esta competición no tiene datos publicados.')
    return { manifest, wraps: entry.wraps, text: await talent.fetchText(entry.file) }
  }, 'El fichero')

/** Who is who across leagues (#996): `links` maps a FBCYL person to the FEB person she IS; `by_feb` says which FBCYL competitions hold rows of a FEB person, so his profile opens only those. */
export interface TalentIdentities { format: number; links: Record<string, string>; by_feb: Record<string, string[]> }

const NO_IDENTITIES: TalentIdentities = { format: 1, links: {}, by_feb: {} }

/** The identities of the publication (empty when it has none: nobody is linked). */
export async function loadIdentities(): Promise<TalentIdentities> {
  if (!(await talent.loadManifest()).identities) return NO_IDENTITIES
  return talent.openSealed<TalentIdentities>(async () => {
    const manifest = await talent.loadManifest()
    if (!manifest.identities) throw new TalentDataUnavailable('Esta publicación no tiene identidades.')
    return { manifest, wraps: manifest.identities.wraps, text: await talent.fetchText(manifest.identities.file) }
  }, 'El fichero')
}
