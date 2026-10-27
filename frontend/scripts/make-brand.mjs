// Writes the icons of the web and the image to share a link from the brand of design/brand (issue #189):
//   npm run brand      (renders with the Chromium of Playwright, already a dependency of the web)
// The results are committed in public/, so the build does not depend on this script: run it when the brand changes.
// src/brand.test.tsx checks that public/ keeps the brand of design/ and the size each place asks for.
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '@playwright/test'

const web = path.resolve(import.meta.dirname, '..')
const brand = path.resolve(web, '../design/brand')
const pub = (file) => path.join(web, 'public', file)
// inlined: a page made with setContent cannot load fonts from file://
const fontUrl = (pkg, file) => `data:font/woff2;base64,${fs.readFileSync(path.join(web, 'node_modules/@fontsource-variable', pkg, 'files', file)).toString('base64')}`
const NAVY = '#1A2744'
const ORANGE = '#f97316'

const iconSvg = fs.readFileSync(path.join(brand, 'web-icon.svg'), 'utf8')
const markSvg = fs.readFileSync(path.join(brand, 'web-mark.svg'), 'utf8')

/** An .ico with PNG entries (Vista+): the header, one entry of 16 bytes per image, then the images. */
function ico(pngs) {
  const header = Buffer.alloc(6 + 16 * pngs.length)
  header.writeUInt16LE(0, 0); header.writeUInt16LE(1, 2); header.writeUInt16LE(pngs.length, 4)
  let offset = header.length
  pngs.forEach(({ size, data }, i) => {
    const at = 6 + 16 * i
    header.writeUInt8(size % 256, at); header.writeUInt8(size % 256, at + 1)
    header.writeUInt16LE(1, at + 4); header.writeUInt16LE(32, at + 6)
    header.writeUInt32LE(data.length, at + 8); header.writeUInt32LE(offset, at + 12)
    offset += data.length
  })
  return Buffer.concat([header, ...pngs.map(p => p.data)])
}

const browser = await chromium.launch(process.env.CI ? {} : { channel: 'chrome' })
const page = await browser.newPage()

async function render(html, width, height, transparent = true) {
  await page.setViewportSize({ width, height })
  await page.setContent(`<!doctype html><html><head><style>html,body{margin:0;width:${width}px;height:${height}px;overflow:hidden;background:transparent}
    svg{display:block;width:${width}px;height:${height}px}</style></head><body>${html}</body></html>`)
  await page.evaluate(() => document.fonts.ready)
  return page.screenshot({ omitBackground: transparent, clip: { x: 0, y: 0, width, height } })
}

const icon = (size) => render(iconSvg, size, size)
fs.copyFileSync(path.join(brand, 'web-icon.svg'), pub('favicon.svg'))
fs.writeFileSync(pub('favicon.ico'), ico(await Promise.all([16, 32, 48].map(async size => ({ size, data: await icon(size) })))))
fs.writeFileSync(pub('apple-touch-icon.png'), await render(iconSvg.replace('rx="22"', 'rx="0"'), 180, 180, false))   // iOS rounds it itself
fs.writeFileSync(pub('icon-192.png'), await icon(192))
fs.writeFileSync(pub('icon-512.png'), await icon(512))

// the image of a shared link: the mark and the name over the navy of the brand
const og = `
  <style>
    @font-face { font-family: 'Space Grotesk'; src: url('${fontUrl('space-grotesk', 'space-grotesk-latin-wght-normal.woff2')}'); font-weight: 300 700 }
    @font-face { font-family: 'Inter'; src: url('${fontUrl('inter', 'inter-latin-wght-normal.woff2')}'); font-weight: 100 900 }
    .card { box-sizing: border-box; width: 1200px; height: 630px; padding: 0 96px; display: flex; align-items: center; gap: 64px;
      background: radial-gradient(circle at 18% 50%, rgba(249,115,22,.22), transparent 42%), ${NAVY}; color: #fff }
    .mark svg { width: 300px; height: 300px }
    .name { font: 700 120px/1 'Space Grotesk'; letter-spacing: -3px }
    .name b { color: ${ORANGE}; font-weight: 700 }
    .tag { margin-top: 28px; font: 500 34px/1.3 'Inter'; color: #d0d7de }
    .tag small { display: block; margin-top: 14px; font-size: 26px; color: #8b949e }
  </style>
  <div class="card">
    <div class="mark">${markSvg}</div>
    <div><div class="name">Basket<b>Lab</b></div>
      <div class="tag">Análisis de baloncesto · FEB y FBCYL<small>Equipos · Jugadoras · Posesiones · Informes</small></div></div>
  </div>`
fs.writeFileSync(pub('og-image.png'), await render(og, 1200, 630, false))

await browser.close()
fs.rmSync(pub('logo.png'), { force: true })                      // the old 512 px PNG of the header
console.log('make-brand: favicon.svg/.ico, apple-touch-icon, icon-192/512 and og-image written to public/')
