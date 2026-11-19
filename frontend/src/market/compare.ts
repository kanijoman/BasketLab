// The comparator of BasketLab Talent (epic #872, B5 #881): two or three players side by side, as plain functions (no React, no network).
//
// Rules that were decided:
//  - players of DIFFERENT leagues, competitions and genders can be compared: each one is read in HIS latest season and competition, and a percentile is always the one of that competition, never
//    a comparison across them (the page says so);
//  - the list is in the address (`?j=feb:1,feb:2`) so it can be shared; at most three players, no repeats;
//  - a FBCYL player linked to a FEB person is that person (`linked_to`, #996): the same person is never shown twice;
//  - what a player does not have is NO DATA (`null`, a dash in the page), never a zero; who cannot be found is said (`missing`), not dropped in silence;
//  - the best of an axis is marked (all the tied ones) only when at least two players have it.
import { bioOf, personRows, RADAR_AXES, trajectory, type Bio } from './player'
import { plain, type SearchRow } from './search'

export const MAX_COMPARED = 3

/** The people of the address, in order, without blanks or repeats, as many as the comparator takes. */
export const parseCompare = (value: string | null): string[] =>
  [...new Set((value ?? '').split(',').map(s => s.trim()).filter(Boolean))].slice(0, MAX_COMPARED)

/** The list with ``id`` added, or taken out when it is there; a full list does not take another one. */
export const toggleCompare = (ids: string[], id: string): string[] =>
  ids.includes(id) ? ids.filter(x => x !== id) : ids.length >= MAX_COMPARED ? ids : [...ids, id]

export interface ComparedPlayer {
  id: string
  name: string
  bio: Bio
  /** The main row of his latest season: the one the figures and percentiles are read from. */
  row: SearchRow
  /** How many seasons his trajectory has (a linked FBCYL season counts). */
  seasons: number
}

/** The player of each id (a linked FBCYL id is the FEB person), in the order asked, and the ids nobody has. */
export function comparePlayers(rows: SearchRow[], ids: string[]): { players: ComparedPlayer[]; missing: string[] } {
  const players: ComparedPlayer[] = []
  const missing: string[] = []
  for (const asked of ids) {
    const id = rows.find(r => r.person_id === asked)?.linked_to ?? asked
    if (players.some(p => p.id === id)) continue
    const mine = personRows(rows, id)
    if (mine.length === 0) { missing.push(asked); continue }
    const seasons = trajectory(mine)
    const bio = bioOf(mine)
    players.push({ id, name: bio.name, bio, row: seasons[seasons.length - 1].main, seasons: seasons.length })
  }
  return { players, missing }
}

export interface CompareCell { text: string | null; best: boolean }
export interface CompareLine { key: string; label: string; group: 'bio' | 'figures' | 'percentiles'; cells: CompareCell[] }

const per = (v: number | undefined | null) => (v === null || v === undefined ? null : v.toFixed(1))
const line = (key: string, label: string, group: CompareLine['group'], texts: (string | null)[]): CompareLine => ({ key, label, group, cells: texts.map(text => ({ text, best: false })) })

/** The rows of the table of the comparison: bio, figures per 40 and the percentile of each axis of the radar. */
export function compareLines(players: ComparedPlayer[]): CompareLine[] {
  const each = (read: (p: ComparedPlayer) => string | null) => players.map(read)
  const bio: CompareLine[] = [
    line('competition', 'Competición', 'bio', each(p => `${p.row.season_label} · ${p.row.competition} · ${p.row.team_name}`)),
    line('age', 'Edad (31/12)', 'bio', each(p => (p.row.age === null ? null : String(p.row.age)))),
    line('height', 'Altura', 'bio', each(p => (p.bio.height.value === null ? null : `${p.bio.height.value} cm`))),
    line('position', 'Posición', 'bio', each(p => p.bio.position.value)),
    line('nationality', 'Nacionalidad', 'bio', each(p => (p.bio.nationalities.length ? p.bio.nationalities.join(' · ') : p.bio.nationality.value))),
  ]
  const figures: CompareLine[] = [
    line('games', 'Partidos', 'figures', each(p => String(p.row.games))),
    line('minutes', 'Minutos', 'figures', each(p => String(Math.round(p.row.minutes / 60)))),
    line('pts40', 'Puntos / 40', 'figures', each(p => per(p.row.per40?.pts))),
    line('ast40', 'Asistencias / 40', 'figures', each(p => per(p.row.per40?.ast))),
    line('reb40', 'Rebotes / 40', 'figures', each(p => (p.row.per40 ? per(p.row.per40.orb + p.row.per40.drb) : null))),
  ]
  const percentiles: CompareLine[] = RADAR_AXES.map(a => {
    const values = players.map(p => p.row.pct?.[a.key] ?? null)
    const known = values.filter((v): v is number => v !== null)
    const top = known.length >= 2 ? Math.max(...known) : null
    return { key: a.key, label: a.label, group: 'percentiles' as const, cells: values.map(v => ({ text: v === null ? null : String(Math.round(v)), best: top !== null && v === top })) }
  })
  return [...bio, ...figures, ...percentiles]
}

export interface Found { id: string; name: string; label: string }

const MIN_LETTERS = 2

/** The people whose name has every word of ``text`` (no accents, any case or order), once each (a linked FBCYL player is the FEB person), described by his latest season; those in ``exclude`` are left out. */
export function findPlayers(rows: SearchRow[], text: string, exclude: string[], limit = 8): Found[] {
  const words = plain(text).split(' ').filter(Boolean)
  if (plain(text).length < MIN_LETTERS) return []
  const latest = new Map<string, SearchRow>()
  for (const r of rows) {
    const id = r.linked_to ?? r.person_id
    const name = plain(`${r.full_name ?? ''} ${r.name}`)
    if (exclude.includes(id) || !words.every(w => name.includes(w))) continue
    const seen = latest.get(id)
    if (!seen || Number(r.season) > Number(seen.season) || (r.season === seen.season && r.minutes > seen.minutes)) latest.set(id, r)
  }
  return [...latest.entries()]
    .map(([id, r]) => ({ id, name: r.full_name ?? r.name, label: `${r.season_label} · ${r.competition} · ${r.team_name}` }))
    .sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id))
    .slice(0, limit)
}
