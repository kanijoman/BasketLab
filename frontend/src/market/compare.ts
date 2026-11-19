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

/** The axes of the radar the comparator draws (#1014): all of them in the fixed order unless the address chooses (`?ejes=tov,pts,ast`); a polygon needs at least three. */
export const DEFAULT_AXES: string[] = RADAR_AXES.map(a => a.key)
export const MIN_AXES = 3

/** The axes of the address, in the order asked for, without repeats or unknown ones; with fewer than three left (or nothing) it is the default. */
export function parseAxes(value: string | null): string[] {
  const keys = [...new Set((value ?? '').split(',').map(s => s.trim()).filter(k => DEFAULT_AXES.includes(k)))]
  return keys.length >= MIN_AXES ? keys : DEFAULT_AXES
}

/** What goes to the address: nothing when the axes are the default, the list otherwise. */
export const axesToParam = (axes: string[]): string | null => (axes.join(',') === DEFAULT_AXES.join(',') ? null : axes.join(','))

/** The axis hidden, or shown again at the end; never leaves fewer than three. */
export function toggleAxis(axes: string[], key: string): string[] {
  if (!axes.includes(key)) return [...axes, key]
  return axes.length <= MIN_AXES ? axes : axes.filter(k => k !== key)
}

/** The axis one place up (-1) or down (1); at the ends it stays. */
export function moveAxis(axes: string[], key: string, by: -1 | 1): string[] {
  const i = axes.indexOf(key)
  const j = i + by
  if (i < 0 || j < 0 || j >= axes.length) return axes
  const out = [...axes]
  ;[out[i], out[j]] = [out[j], out[i]]
  return out
}

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

export interface CompareCell { text: string | null; best: boolean; value: number | null }
/** ``diff``: the second player minus the first, as text, only with exactly two players and a number in both (null otherwise). */
export interface CompareLine { key: string; label: string; group: 'bio' | 'figures' | 'percentiles'; cells: CompareCell[]; diff: string | null }

/** A line from the number of each player (null where he has none): the text and the difference are made from it, with the decimals of the line. */
function numeric(key: string, label: string, group: CompareLine['group'], values: (number | null)[], decimals: number, text: (v: number) => string = v => v.toFixed(decimals)): CompareLine {
  const cells = values.map(v => ({ text: v === null ? null : text(v), best: false, value: v }))
  const [a, b] = values
  return { key, label, group, cells, diff: values.length === 2 && a !== null && b !== null ? signed(b - a, decimals) : null }
}

/** ``+3``, ``−1.5`` (a real minus) or ``0``; a difference that rounds to nothing is ``0``. */
function signed(d: number, decimals: number): string {
  const text = Math.abs(d).toFixed(decimals)
  return Number(text) === 0 ? '0' : `${d > 0 ? '+' : '−'}${text}`
}

const words = (key: string, label: string, group: CompareLine['group'], texts: (string | null)[]): CompareLine =>
  ({ key, label, group, cells: texts.map(text => ({ text, best: false, value: null })), diff: null })

/** The rows of the table of the comparison: bio, figures per 40 and the percentile of each axis of the radar that is chosen (``axes``, all by default). */
export function compareLines(players: ComparedPlayer[], axes: string[] = DEFAULT_AXES): CompareLine[] {
  const each = <T,>(read: (p: ComparedPlayer) => T) => players.map(read)
  const bio: CompareLine[] = [
    words('competition', 'Competición', 'bio', each(p => `${p.row.season_label} · ${p.row.competition} · ${p.row.team_name}`)),
    numeric('age', 'Edad (31/12)', 'bio', each(p => p.row.age), 0),
    numeric('height', 'Altura', 'bio', each(p => p.bio.height.value), 0, v => `${v} cm`),
    words('position', 'Posición', 'bio', each(p => p.bio.position.value)),
    words('nationality', 'Nacionalidad', 'bio', each(p => (p.bio.nationalities.length ? p.bio.nationalities.join(' · ') : p.bio.nationality.value))),
  ]
  const figures: CompareLine[] = [
    numeric('games', 'Partidos', 'figures', each(p => p.row.games), 0),
    numeric('minutes', 'Minutos', 'figures', each(p => Math.round(p.row.minutes / 60)), 0),
    numeric('pts40', 'Puntos / 40', 'figures', each(p => p.row.per40?.pts ?? null), 1),
    numeric('ast40', 'Asistencias / 40', 'figures', each(p => p.row.per40?.ast ?? null), 1),
    numeric('reb40', 'Rebotes / 40', 'figures', each(p => (p.row.per40 ? p.row.per40.orb + p.row.per40.drb : null)), 1),
  ]
  const percentiles: CompareLine[] = axes.flatMap(k => RADAR_AXES.filter(a => a.key === k)).map(a => {
    const line = numeric(a.key, a.label, 'percentiles', each(p => p.row.pct?.[a.key] ?? null), 0, v => String(Math.round(v)))
    const known = line.cells.map(c => c.value).filter((v): v is number => v !== null)
    const top = known.length >= 2 ? Math.max(...known) : null
    return { ...line, cells: line.cells.map(c => ({ ...c, best: top !== null && c.value === top })) }
  })
  return [...bio, ...figures, ...percentiles]
}

/** The comparison as a table to export: ``Dato``, a column per player and ``Diferencia`` when there are exactly two; an empty cell where there is no data. */
export function compareCsv(players: ComparedPlayer[], lines: CompareLine[]): { headers: { key: string; label: string }[]; data: Record<string, string>[] } {
  const withDiff = players.length === 2
  const headers = [{ key: 'dato', label: 'Dato' }, ...players.map((p, i) => ({ key: `p${i}`, label: p.name })), ...(withDiff ? [{ key: 'diff', label: 'Diferencia' }] : [])]
  const data = lines.map(l => ({ dato: l.label, ...Object.fromEntries(l.cells.map((c, i) => [`p${i}`, c.text ?? ''])), ...(withDiff ? { diff: l.diff ?? '' } : {}) }))
  return { headers, data }
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
