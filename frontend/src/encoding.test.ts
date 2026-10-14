/// <reference types="node" />
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

// Mojibake = UTF-8 text that was read as Windows-1252 and saved again: an en dash turns into three odd characters and an
// accented letter into two. The patterns are built from character codes so this file never contains them itself.
const chars = (...codes: number[]) => String.fromCharCode(...codes)
const range = (from: number, to: number) => `${chars(from)}-${chars(to)}`
const LEADS = chars(0xc3, 0xc2)                       // first character of a re-read two-byte letter
const FOLLOWERS = `${range(0x80, 0xbf)}${range(0x2018, 0x203a)}${chars(0x152, 0x153, 0x160, 0x161, 0x178, 0x17d, 0x17e, 0x192, 0x2c6, 0x2dc)}`
const MOJIBAKE = [
  new RegExp(chars(0xe2, 0x20ac)),                    // start of a re-read punctuation mark such as the en dash
  new RegExp(chars(0xe2, 0x201d)),                    // start of a re-read box-drawing character
  new RegExp(`[${LEADS}][${FOLLOWERS}]`),             // re-read accented letters
]
const hasMojibake = (text: string) => MOJIBAKE.some(re => re.test(text))

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return /\.(tsx?|css|json)$/.test(entry.name) ? [path] : []
  })
}

describe('source encoding', () => {
  // Regression (#185): the home card showed a garbled dash in the collection label because HomePage.tsx had been saved twice.
  it('has no mojibake in any source file of the frontend', () => {
    const offenders = sourceFiles(__dirname).filter(file => hasMojibake(readFileSync(file, 'utf8')))
    expect(offenders.map(f => f.slice(__dirname.length + 1))).toEqual([])
  })

  it('detects the garbled dash and the garbled accent it was written for', () => {
    expect(hasMojibake(`Liga ${chars(0xe2, 0x20ac, 0x201c)} B`)).toBe(true)
    expect(hasMojibake(`Preparaci${chars(0xc3, 0xb3)}n`)).toBe(true)
    expect(hasMojibake('Preparación – B ── →')).toBe(false)
  })
})
