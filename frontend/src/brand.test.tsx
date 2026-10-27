/// <reference types="node" />
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import BrandLogo from './components/BrandLogo'

// Issue #189: the brand of the web. The sources live in design/brand (shared with the live app); `npm run brand` writes the
// icons and the image to share a link into public/. These checks keep both in step and the page saying what it is.
const ROOT = join(__dirname, '..')
const BRAND = join(ROOT, '..', 'design', 'brand')
const page = readFileSync(join(ROOT, 'index.html'), 'utf8')
const pub = (file: string) => join(ROOT, 'public', file)
const pngSize = (file: string) => { const b = readFileSync(file); return [b.readUInt32BE(16), b.readUInt32BE(20)] }

describe('brand of the web (issue #189)', () => {
  it('the page says what it is when its link is shared', () => {
    expect(page).toMatch(/<title>BasketLab · [^<]+<\/title>/)
    for (const tag of ['name="description"', 'property="og:title"', 'property="og:description"', 'property="og:type" content="website"',
      'property="og:image" content="/og-image.png"', 'property="og:locale" content="es_ES"', 'name="twitter:card" content="summary_large_image"']) {
      expect(page).toContain(tag)
    }
  })

  it('the browser finds the icons: SVG first, ICO for the old ones, the Apple one and the manifest', () => {
    expect(page).toContain('<link rel="icon" type="image/svg+xml" href="/favicon.svg" />')
    expect(page).toContain('<link rel="icon" href="/favicon.ico" sizes="48x48" />')
    expect(page).toContain('<link rel="apple-touch-icon" href="/apple-touch-icon.png" />')
    expect(page).toContain('<link rel="manifest" href="/manifest.webmanifest" />')
  })

  it('the icons of public/ are the ones of design/brand, at the size each place asks for', () => {
    expect(readFileSync(pub('favicon.svg'), 'utf8')).toBe(readFileSync(join(BRAND, 'web-icon.svg'), 'utf8'))
    expect(pngSize(pub('apple-touch-icon.png'))).toEqual([180, 180])
    expect(pngSize(pub('icon-192.png'))).toEqual([192, 192])
    expect(pngSize(pub('icon-512.png'))).toEqual([512, 512])
    expect(pngSize(pub('og-image.png'))).toEqual([1200, 630])
    const ico = readFileSync(pub('favicon.ico'))
    expect([ico.readUInt16LE(0), ico.readUInt16LE(2)]).toEqual([0, 1])            // an icon file
    expect(ico.readUInt16LE(4)).toBe(3)                                          // 16, 32 and 48 px
    expect(existsSync(pub('logo.png'))).toBe(false)                              // the old 512 px PNG, almost invisible at 28 px
  })

  it('the manifest names the web and points at icons that exist', () => {
    const manifest = JSON.parse(readFileSync(pub('manifest.webmanifest'), 'utf8'))
    expect(manifest).toMatchObject({ name: 'BasketLab', short_name: 'BasketLab', lang: 'es', start_url: '/', display: 'standalone' })
    expect(manifest.icons.map((i: { src: string }) => i.src)).toEqual(['/icon-192.png', '/icon-512.png', '/favicon.svg'])
    for (const icon of manifest.icons) expect(existsSync(pub(icon.src.slice(1))), icon.src).toBe(true)
  })
})

describe('BrandLogo (issue #189)', () => {
  it('shows the mark and the name, and the mark is never hidden', () => {
    const { container } = render(<BrandLogo />)
    const mark = container.querySelector('img')!
    expect(mark.getAttribute('src')).toMatch(/web-icon\.svg$|^data:image\/svg\+xml/)    // Vite inlines a small SVG
    expect(mark).toHaveAttribute('alt', '')                                      // the name is the text next to it
    fireEvent.error(mark)
    expect(mark.style.display).not.toBe('none')
    expect(screen.getByText('Basket')).toBeInTheDocument()
    expect(screen.getByText('Lab')).toBeInTheDocument()
  })
})
