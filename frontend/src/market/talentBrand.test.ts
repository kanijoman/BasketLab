/// <reference types="node" />
/** The brand of BasketLab Talent (#901): the ball of the suite with a magnifying glass (search for talent). Sources in design/brand, icons written by `npm run brand` into public/talent. */
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const ROOT = join(__dirname, '..', '..')
const BRAND = join(ROOT, '..', 'design', 'brand')
const brand = (file: string) => readFileSync(join(BRAND, file), 'utf8')
const pub = (file: string) => join(ROOT, 'public', 'talent', file)
const pngSize = (file: string) => { const b = readFileSync(file); return [b.readUInt32BE(16), b.readUInt32BE(20)] }
const PALETTE = new Set(['#E8651A', '#111111', '#1A2744', '#FFFFFF'])          // the colours of the ball and of the navy of the suite: nothing loose

describe('mark of BasketLab Talent', () => {
  const mark = brand('talent-mark.svg')

  it('is the ball of the suite with a lens and a handle, and not the trend line of Analytics', () => {
    expect(mark).toContain('<circle cx="50" cy="50" r="38" fill="#E8651A"/>')       // the same ball as web-mark.svg and live-mark.svg
    expect(mark).toContain('data-part="lens"')
    expect(mark).toContain('data-part="handle"')
    expect(mark).not.toContain('M 8 70 L 32 58 L 48 64 L 80 34')
    expect(mark).not.toContain('<rect')                                              // no tile: it goes over any page
  })

  it('uses only the colours of the brand', () => {
    for (const file of ['talent-mark.svg', 'talent-icon.svg']) {
      const colours = brand(file).match(/#[0-9A-Fa-f]{6}\b/g) ?? []
      expect(colours.length).toBeGreaterThan(0)
      for (const c of colours) expect(PALETTE.has(c.toUpperCase()), `${file}: ${c}`).toBe(true)
    }
  })

  it('has a tile version for the places that ask for a square and a one-colour version', () => {
    expect(brand('talent-icon.svg')).toContain('<rect width="100" height="100" rx="22" fill="#1A2744"/>')
    const mono = brand('talent-mono.svg')
    expect(mono).toContain('currentColor')
    expect(mono).not.toMatch(/#[0-9A-Fa-f]{6}/)
    expect(mono).toContain('data-part="lens"')
  })
})

describe('icons of BasketLab Talent in public/talent', () => {
  it('are the sources of design/brand at the size each place asks for', () => {
    expect(readFileSync(pub('favicon.svg'), 'utf8')).toBe(brand('talent-mark.svg'))
    expect(pngSize(pub('apple-touch-icon.png'))).toEqual([180, 180])
    expect(pngSize(pub('icon-192.png'))).toEqual([192, 192])
    expect(pngSize(pub('icon-512.png'))).toEqual([512, 512])
    expect(pngSize(pub('og-image.png'))).toEqual([1200, 630])
    const ico = readFileSync(pub('favicon.ico'))
    expect([ico.readUInt16LE(0), ico.readUInt16LE(2), ico.readUInt16LE(4)]).toEqual([0, 1, 3])      // an icon file with 16, 32 and 48 px
  })

  it('are the ones market.html links, and the page does not borrow the ones of Analytics', () => {
    const page = readFileSync(join(ROOT, 'market.html'), 'utf8')
    for (const tag of ['href="/talent/favicon.svg"', 'href="/talent/favicon.ico"', 'href="/talent/apple-touch-icon.png"', 'content="/talent/og-image.png"']) expect(page).toContain(tag)
    expect(page).not.toMatch(/(href|content)="\/(favicon|apple-touch-icon|og-image)/)
    for (const file of ['favicon.svg', 'favicon.ico', 'apple-touch-icon.png', 'og-image.png']) expect(existsSync(pub(file)), file).toBe(true)
  })
})
