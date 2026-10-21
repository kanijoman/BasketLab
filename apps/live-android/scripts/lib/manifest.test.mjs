// @vitest-environment node
// The list of demo matches the app can replay: every recording of tests/recordings/ that has its package,
// newest first (the newest is the app's default match, issue #223).
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import zlib from 'node:zlib'
import { afterEach, describe, expect, it } from 'vitest'
import { buildManifest, competitionOfCollection, parseStart, titleCase } from './manifest.mjs'

const repoRecordings = path.resolve(import.meta.dirname, '../../../../tests/recordings')
const tmp = []
afterEach(() => { for (const dir of tmp.splice(0)) fs.rmSync(dir, { recursive: true, force: true }) })

function recordingsDir(entries) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'rec-'))
  tmp.push(dir)
  for (const [code, { starttime, home, away, withPackage = true, collection }] of Object.entries(entries)) {
    const pack = { v: 1, match: code, base: { HEADER: { starttime, TEAM: [{ id: home[0], name: home[1] }, { id: away[0], name: away[1] }] } }, lines: [], shots: [], frames: [], gaps: {} }
    fs.writeFileSync(path.join(dir, `${code}.rec.json.gz`), zlib.gzipSync(JSON.stringify(pack)))
    const pkg = collection ? JSON.stringify({ checksum: 'x', package: { collection, team: { id: home[0], name: home[1] } } }) : '{}'
    if (withPackage) fs.writeFileSync(path.join(dir, `${code}.package.json`), pkg)
  }
  return dir
}

describe('parseStart', () => {
  it('turns the FEB start text into an ISO local date-time', () => {
    expect(parseStart('10-10-2026 - 17:00')).toBe('2026-10-10T17:00')
  })

  it('a text it does not understand sorts last instead of crashing', () => {
    expect(parseStart('mañana')).toBe('')
    expect(parseStart(undefined)).toBe('')
  })
})

describe('titleCase', () => {
  it('writes team names like a person would, keeping abbreviations', () => {
    expect(titleCase('MIPELLETYMAS B.F. LEON')).toBe('Mipelletymas B.F. Leon')
    expect(titleCase('RECOLETAS ZAMORA')).toBe('Recoletas Zamora')
  })
})

describe('buildManifest', () => {
  it('lists the real recording of Zamora - Leon with the local team first', () => {
    const [match] = buildManifest(repoRecordings)
    expect(match).toMatchObject({
      code: '2524470', date: '2026-10-10T17:00', recording: '2524470.recording.json', package: '2524470.package.json',
      home: { id: '1008898', name: 'RECOLETAS ZAMORA' }, away: { id: '1008631', name: 'MIPELLETYMAS B.F. LEON' },
    })
    expect(match.title).toBe('Recoletas Zamora – Mipelletymas B.F. Leon')
  })

  it('orders the matches newest first: the first one is the default of the app', () => {
    const dir = recordingsDir({
      100: { starttime: '03-10-2026 - 18:00', home: ['1', 'A'], away: ['2', 'B'] },
      300: { starttime: '17-10-2026 - 20:30', home: ['3', 'C'], away: ['4', 'D'] },
      200: { starttime: '10-10-2026 - 17:00', home: ['5', 'E'], away: ['6', 'F'] },
    })
    expect(buildManifest(dir).map(m => m.code)).toEqual(['300', '200', '100'])
  })

  it('skips a recording without its package (the engine cannot play it)', () => {
    const dir = recordingsDir({
      100: { starttime: '03-10-2026 - 18:00', home: ['1', 'A'], away: ['2', 'B'], withPackage: false },
      200: { starttime: '10-10-2026 - 17:00', home: ['5', 'E'], away: ['6', 'F'] },
    })
    expect(buildManifest(dir).map(m => m.code)).toEqual(['200'])
  })

  it('an empty or missing folder gives an empty list (the app falls back to the sample match)', () => {
    expect(buildManifest(recordingsDir({}))).toEqual([])
    expect(buildManifest(path.join(os.tmpdir(), 'does-not-exist-xyz'))).toEqual([])
  })
})

describe('competitionOfCollection (issue #441)', () => {
  it('reads the competition and the group from the name of the collection', () => {
    expect(competitionOfCollection('SEGUNDA_FEB_2026_2027_Liga_Regular_A')).toBe('SEGUNDA FEB · Liga Regular A')
    expect(competitionOfCollection('TERCERA_FEB_2026_2027_Liga_Regular_A-B')).toBe('TERCERA FEB · Liga Regular A-B')
  })

  it('a name without season is shown as it is, and nothing is empty', () => {
    expect(competitionOfCollection('LIGA_NUEVA')).toBe('LIGA NUEVA')
    expect(competitionOfCollection(undefined)).toBe('')
  })
})

describe('buildManifest with the demos of the teams of interest (issue #441)', () => {
  const entries = {
    100: { starttime: '03-10-2026 - 18:00', home: ['1', 'A'], away: ['2', 'B'], collection: 'LF_CHALLENGE_2026_2027_Liga_Regular_Unico' },
    300: { starttime: '18-10-2026 - 20:30', home: ['3', 'C'], away: ['4', 'D'], collection: 'SEGUNDA_FEB_2026_2027_Liga_Regular_A' },
    200: { starttime: '10-10-2026 - 17:00', home: ['5', 'E'], away: ['6', 'F'] },
  }

  it('each match tells its competition and the team whose package it carries', () => {
    const match = buildManifest(recordingsDir(entries)).find(m => m.code === '300')
    expect(match).toMatchObject({ competition: 'SEGUNDA FEB · Liga Regular A', teamId: '3' })
  })

  it('a package without that data leaves them out and the match still works', () => {
    const match = buildManifest(recordingsDir(entries)).find(m => m.code === '200')
    expect(match.competition).toBe('')
    expect(match.teamId).toBe('')
  })

  it('the default match of demos.json comes first, however old it is; the rest stay newest first', () => {
    const dir = recordingsDir(entries)
    fs.writeFileSync(path.join(dir, 'demos.json'), JSON.stringify({ default: '100' }))
    expect(buildManifest(dir).map(m => m.code)).toEqual(['100', '300', '200'])
  })

  it('a default that is not there, or a broken demos.json, falls back to the newest', () => {
    const dir = recordingsDir(entries)
    fs.writeFileSync(path.join(dir, 'demos.json'), JSON.stringify({ default: '999' }))
    expect(buildManifest(dir).map(m => m.code)).toEqual(['300', '200', '100'])
    fs.writeFileSync(path.join(dir, 'demos.json'), 'no json')
    expect(buildManifest(dir).map(m => m.code)).toEqual(['300', '200', '100'])
  })

  it('the real recordings of the repository keep Zamora - Leon as the default and include the demos of the teams of interest', () => {
    const codes = buildManifest(repoRecordings).map(m => m.code)
    expect(codes[0]).toBe('2524470')
    expect(codes).toEqual(expect.arrayContaining(['2536133', '2536311', '2536851']))
  })
})
