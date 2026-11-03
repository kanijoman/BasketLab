import { afterEach, describe, expect, it, vi } from 'vitest'
import { PAPER } from '@design/paper'
import { courtSvg, paperChartTheme } from './scoutingCharts'
import { svgToPng, svgSize } from './svgImage'
import type { ShotRawData, ShotZoneData } from '@/api/client'

// The shot charts of the individual scouting (issue #717, 17c): the court of the web drawn with the colours of the paper (the DOCX is white whatever theme the screen is in) and made an
// image the DOCX can hold. The drawing is the web's own `FibaCourtSVG`; here it is checked for what the document needs from it.
const ZONES: ShotZoneData[] = [
  { zone: 'restricted_area', zone_label: 'Zona Restringida', points: 2, fga: 20, fgm: 14, fg_pct: 70, rating: 'above', low_sample: false },
  { zone: 'top_three', zone_label: 'Triple Centro', points: 3, fga: 12, fgm: 3, fg_pct: 25, rating: 'below', low_sample: false },
  { zone: 'mid_left', zone_label: 'Media Izquierda', points: 2, fga: 4, fgm: 2, fg_pct: 50, rating: 'average', low_sample: true },
] as ShotZoneData[]
const SHOTS: ShotRawData[] = [{ x: 7.5, y: 2, made: true, zone: 'restricted_area' }, { x: 3, y: 5, made: false, zone: 'mid_left' }, { x: 7.5, y: 9, made: false, zone: 'top_three' }]

describe('the colours are those of the paper', () => {
  it('has every colour of the chart theme from design/paper.ts, none from the screen', () => {
    const theme = paperChartTheme()
    expect([theme.ok, theme.bad, theme.warn, theme.text, theme.axis, theme.floor, theme.onData, theme.faint]).toEqual([PAPER.ok, PAPER.bad, PAPER.warn, PAPER.ink, PAPER.muted, PAPER.surfaceRaised, PAPER.onData, PAPER.faint])
    expect(theme.series).toHaveLength(8)
    expect(theme.series.every(c => /^#[0-9a-f]{6}$/.test(c))).toBe(true)
  })
})

describe('the court as an image of the DOCX', () => {
  it('draws the zones with their percentage, the shots and the rating colours of the paper, as a standalone SVG', () => {
    const svg = courtSvg('zones', ZONES, [])
    expect(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"')).toBe(true)
    expect(svg).toContain('font-family="Helvetica')
    for (const text of ['70%', '25%', '20T', 'Por encima de la liga']) expect(svg).toContain(text)
    for (const colour of [PAPER.ok, PAPER.bad, PAPER.warn]) expect(svg).toContain(colour)
    expect(svg).toContain(`background:${PAPER.surfaceRaised}`)
  })

  it('draws the heatmap from the shots with the blurred layers, one pair of dots per shot', () => {
    const svg = courtSvg('heatmap', [], SHOTS)
    expect(svg).toContain('feGaussianBlur')
    expect((svg.match(/<circle/g) ?? []).length).toBeGreaterThanOrEqual(SHOTS.length * 2)
  })

  it('has a size to rasterise', () => {
    expect(svgSize(courtSvg('zones', ZONES, []))).toEqual({ width: 450, height: 420 })
    expect(svgSize('<svg viewBox="0 0 640 540" width="640" height="540"></svg>')).toEqual({ width: 640, height: 540 })
    expect(svgSize('<svg></svg>')).toBeNull()
  })
})

describe('the PNG', () => {
  afterEach(() => vi.restoreAllMocks())

  function stubBrowser(blob: Blob | null) {
    const drawn: unknown[][] = []
    const context = { fillStyle: '', fillRect: (...a: unknown[]) => drawn.push(['fillRect', ...a]), drawImage: (...a: unknown[]) => drawn.push(['drawImage', ...a]), scale: vi.fn() }
    const canvas = { width: 0, height: 0, getContext: () => context, toBlob: (cb: (b: Blob | null) => void) => cb(blob) }
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string) => (tag === 'canvas' ? canvas : document.createElementNS('http://www.w3.org/1999/xhtml', tag))) as never)
    class FakeImage {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      set src(_value: string) { queueMicrotask(() => this.onload?.()) }
    }
    vi.stubGlobal('Image', FakeImage)
    return { canvas, drawn }
  }

  it('is drawn on a white canvas of the size of the image times the scale and returns the bytes', async () => {
    const { canvas, drawn } = stubBrowser(new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }))
    const png = await svgToPng('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 420" width="450" height="420"></svg>', 2)
    expect(Array.from(png)).toEqual([137, 80, 78, 71])
    expect([canvas.width, canvas.height]).toEqual([900, 840])
    expect(drawn[0]).toEqual(['fillRect', 0, 0, 900, 840])                         // white first: a transparent PNG goes black in some viewers
    expect(drawn[1][0]).toBe('drawImage')
  })

  it('fails when the canvas gives no PNG or the image cannot be loaded', async () => {
    stubBrowser(null)
    await expect(svgToPng('<svg viewBox="0 0 10 10" width="10" height="10"></svg>', 1)).rejects.toThrow(/PNG/)
    await expect(svgToPng('<svg></svg>', 1)).rejects.toThrow(/tamaño/)
  })
})
