import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createRef } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ExportButton from './ExportButton'

// Issue #617: since U0 (#188) the capture of the page follows the theme in use, but the PDF painted every page dark and its title in light
// colours, fixed: in the light theme (the default) a light capture sat in a dark frame. The page follows the theme now (decision of
// 27/10/2026). jsPDF is the boundary: a fake that records what is painted.
const calls = vi.hoisted(() => [] as [string, unknown[]][])
vi.mock('jspdf', () => ({
  jsPDF: class {
    setFillColor(...a: unknown[]) { calls.push(['fill', a]) }
    rect(...a: unknown[]) { calls.push(['rect', a]) }
    setTextColor(...a: unknown[]) { calls.push(['ink', a]) }
    setFontSize() { /* size only */ }
    text(...a: unknown[]) { calls.push(['text', a]) }
    addPage() { calls.push(['page', []]) }
    addImage() { /* the capture */ }
    save(...a: unknown[]) { calls.push(['save', a]) }
  },
}))

// the real tokens are not loaded in jsdom: the three the PDF reads, in both themes
const TOKENS = `
  :root[data-theme="light"] { --bg: #f6f8fa; --text: #1f2328; --text-muted: #59636e }
  :root[data-theme="dark"]  { --bg: #0d1117; --text: #e6edf3; --text-muted: #8b949e }
`
let style: HTMLStyleElement
beforeEach(() => {
  calls.length = 0
  style = document.createElement('style')
  style.textContent = TOKENS
  document.head.appendChild(style)
})
afterEach(() => {
  style.remove()
  document.documentElement.removeAttribute('data-theme')
  vi.unstubAllGlobals()
})

async function exportPdf() {
  render(<ExportButton pdfTitle="Estadísticas de Equipo" />)
  fireEvent.click(screen.getByRole('button', { name: /Exportar/ }))
  fireEvent.click(screen.getByRole('button', { name: /PDF/ }))
  await waitFor(() => expect(calls.some(([what]) => what === 'save')).toBe(true))
}

/** The colour of the ink set last before `text` was written */
function inkOf(text: string): unknown {
  const at = calls.findIndex(([what, args]) => what === 'text' && String(args[0]).startsWith(text))
  return calls.slice(0, at).reverse().find(([what]) => what === 'ink')?.[1][0]
}

describe('the PDF follows the theme in use (issue #617)', () => {
  it.each([
    ['light', '#f6f8fa', '#1f2328', '#59636e'],
    ['dark', '#0d1117', '#e6edf3', '#8b949e'],
  ])('%s: the page, the title and the date take the colours of the theme', async (theme, page, ink, muted) => {
    document.documentElement.setAttribute('data-theme', theme)
    await exportPdf()
    expect(calls.find(([what]) => what === 'fill')?.[1]).toEqual([page])
    expect(inkOf('Estadísticas de Equipo')).toBe(ink)
    expect(inkOf('BasketLab ·')).toBe(muted)
  })
})

describe('a chart exported from its SVG (issue #617)', () => {
  it('gets the background of the theme in use, not a transparent one', async () => {
    document.documentElement.setAttribute('data-theme', 'light')
    const painted: [string, unknown][] = []
    const context = {
      scale: () => undefined,
      fillRect: (...a: unknown[]) => painted.push(['fillRect', a]),
      drawImage: () => painted.push(['chart', null]),
      set fillStyle(v: string) { painted.push(['fillStyle', v]) },
    }
    const create = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string) => tag === 'canvas'
      ? Object.assign(create('canvas'), { getContext: () => context, toBlob: () => undefined })
      : create(tag)) as typeof document.createElement)
    vi.stubGlobal('Image', class { onload: (() => void) | null = null; set src(_: string) { setTimeout(() => this.onload?.()) } })
    URL.createObjectURL = vi.fn(() => 'blob:chart')
    URL.revokeObjectURL = vi.fn()

    const ref = createRef<SVGSVGElement>()
    render(<><svg ref={ref} /><ExportButton captureRef={ref} /></>)
    fireEvent.click(screen.getByRole('button', { name: /Exportar/ }))
    fireEvent.click(screen.getByRole('button', { name: /PNG/ }))
    await waitFor(() => expect(painted.some(([what]) => what === 'chart')).toBe(true))
    expect(painted.findIndex(([what, v]) => what === 'fillStyle' && v === '#f6f8fa')).toBeGreaterThan(-1)
    expect(painted.findIndex(([what]) => what === 'fillRect')).toBeLessThan(painted.findIndex(([what]) => what === 'chart'))
    vi.restoreAllMocks()
  })
})
