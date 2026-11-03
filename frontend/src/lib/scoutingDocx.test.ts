import { describe, expect, it } from 'vitest'
import { strFromU8, unzipSync } from 'fflate'
import { ageOn, playerTables, scoutingDocx } from './scoutingDocx'
import type { PlayerStat } from '@/api/client'
import type { TeamImages } from '@/webdata/client'
import vectors from '../../../tests/local_vectors/scouting_docx.json'

// The DOCX of the individual scouting in the browser (issue #717, 17b). What the tables say (columns, text of the cells, quartile fill) is decided by `scouting_docx_tables.player_tables` on the
// server; `tests/local_vectors/scouting_docx_vectors.py` ran it for every player of two leagues and the web must say the same, to the last digit.
describe('the tables of a player say what the server says', () => {
  it.each(vectors.leagues.map(l => [l.name, l] as const))('%s', (_name, league) => {
    const players = league.players as unknown as PlayerStat[]
    players.forEach((player, i) => expect(playerTables(player, players)).toEqual(league.expected[i]))
  })
})

describe('the age of a player is that of the day the document is made', () => {
  it.each([
    ['05/03/1998', '2026-03-04', 27], ['05/03/1998', '2026-03-05', 28],                       // the day before and the day of the birthday
    ['29/02/2000', '2027-02-28', 26], ['29/02/2000', '2027-03-01', 27],                       // born on a leap day
    ['1/2/2001', '2026-11-03', 25], ['17-11-2001', '2026-11-16', 24],
  ])('%s on %s is %i', (birth, today, age) => expect(ageOn(birth, new Date(`${today}T12:00:00`))).toBe(age))
  it.each([[null], [''], ['sin fecha'], ['31/02/2000'], ['05/13/2000']])('%s has no age', birth => expect(ageOn(birth, new Date('2026-11-03T12:00:00'))).toBeNull())
})

const PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
const JPEG = 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA='

const players = vectors.leagues[0].players as unknown as PlayerStat[]
const team = players.filter(p => p.team_name === players[0].team_name)
const images: TeamImages = {
  format: 1, collection: 'X', team_id: String(players[0].team_id), team: players[0].team_name, logo: PNG,
  players: Object.fromEntries(team.map((p, i) => [String(p.player_id), { name: p.player_name, no: String(i + 4), photo: i === 0 ? JPEG : null, birth_date: i === 0 ? '05/03/1998' : null, height: i === 0 ? '198 cm' : null }])),
}

async function parts(blob: Blob) {
  const files = unzipSync(new Uint8Array(await blob.arrayBuffer()))
  return { xml: strFromU8(files['word/document.xml']), media: Object.keys(files).filter(f => f.startsWith('word/media/')) }
}

describe('the document', () => {
  it('is a DOCX with a page per player: the header, the identity with the age, the three tables with their fills and the notes', async () => {
    const blob = await scoutingDocx({ players, teamName: players[0].team_name, images, today: new Date('2026-03-05T12:00:00'), date: '05/03/2026' })
    expect(blob.type).toBe('application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    const { xml, media } = await parts(blob)
    for (const word of ['Scouting Individual', players[0].team_name, '05/03/2026', '1. Estadística General', 'Promedios por partido:', 'Totales acumulados:', '2. Estadística Avanzada',
      '5. Notas del cuerpo técnico', 'Nac.', '05/03/1998', '28 años', '198 cm', 'Posición', '[FOTO]']) expect(xml).toContain(word)
    expect((xml.match(/w:type="page"/g) ?? []).length).toBe(team.length - 1)                // a page break between players, not after the last
    expect((xml.match(/Notas del cuerpo técnico/g) ?? []).length).toBe(team.length)
    expect(xml).toMatch(/w:fill="(C6EFCE|FFEB9C|FFD9B3|FFC7CE)"/)
    expect(media.length).toBeGreaterThanOrEqual(2)                                            // the crest and the photo (the library keeps one copy of a repeated image)
  })

  it('is made without the images, the birth date or the height (older seasons, FBCYL): blanks and the placeholder, and no failure', async () => {
    const { xml, media } = await parts(await scoutingDocx({ players, teamName: players[0].team_name, images: null, today: new Date('2026-03-05T12:00:00'), date: '05/03/2026' }))
    expect(media).toEqual([])
    expect(xml).toContain('___________')
    expect(xml).toContain('[FOTO]')
    expect(xml).toContain(players[0].team_name)
  })

  it('holds the charts of a player where he has them: the shooting profile (heatmap and zones) and the radar, each under its heading, and none where he has none', async () => {
    const png = Uint8Array.from(atob(PNG.split(',')[1]), c => c.charCodeAt(0))
    const charts = { [String(team[0].player_id)]: { heatmap: png, zones: png, radar: png }, [String(team[1].player_id)]: { radar: png } }
    const { xml, media } = await parts(await scoutingDocx({ players, teamName: players[0].team_name, images: null, charts, today: new Date('2026-03-05T12:00:00'), date: '05/03/2026' }))
    expect((xml.match(/3\. Perfil de Lanzamiento/g) ?? []).length).toBe(1)                // the player with no shots has no profile section
    expect((xml.match(/4\. Perfil de Juego/g) ?? []).length).toBe(2)
    expect((xml.match(/<w:pageBreakBefore/g) ?? []).length).toBe(2)                        // the radar starts a page, as it always did
    expect(media.length).toBeGreaterThanOrEqual(1)
    expect((xml.match(/<w:drawing>/g) ?? []).length).toBe(4)
    expect(xml.indexOf('3. Perfil de Lanzamiento')).toBeLessThan(xml.indexOf('4. Perfil de Juego'))
    expect(xml.indexOf('4. Perfil de Juego')).toBeLessThan(xml.indexOf('5. Notas del cuerpo técnico'))
  })

  it('finds the photo of an FBCYL player by his uuid (his player_id changes from game to game), with no birth date nor height', async () => {
    const fbcyl = team.map((p, i) => ({ ...p, player_id: 900 + i, player_uuid: `uuid-${i}` })) as unknown as PlayerStat[]
    const imgs: TeamImages = { ...images, players: { 'uuid-0': { name: 'X', no: '11', photo: JPEG, birth_date: null, height: null } } }
    const { xml, media } = await parts(await scoutingDocx({ players: fbcyl, teamName: fbcyl[0].team_name, images: imgs, today: new Date('2026-03-05T12:00:00'), date: '05/03/2026' }))
    expect(xml).toContain('#11')                                                  // the dorsal of the published file, found by uuid
    expect(media.length).toBeGreaterThanOrEqual(2)                                // crest and photo
    expect(xml).toContain('___________')                                          // the age and the height stay blank
  })

  it('has nothing to say for a team without players', async () => {
    await expect(scoutingDocx({ players, teamName: 'NO EXISTE', images: null, today: new Date(), date: '' })).rejects.toThrow(/jugadores/)
  })
})
