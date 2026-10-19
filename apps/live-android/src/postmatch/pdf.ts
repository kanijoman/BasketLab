/** Draws the blocks of a post-match report on A4 pages with jsPDF (issue #409). Loaded on demand: the library is only needed when a
 *  report is asked for, so the app starts as light as before. Everything is drawn from the tablet, with no network. */
import type { jsPDF } from 'jspdf'
import { safeText, type Block } from './blocks'

const PAGE = { w: 210, h: 297 }
const MARGIN = 15
const WIDTH = PAGE.w - 2 * MARGIN
const BOTTOM = PAGE.h - 18          // the footer lives under this line
const LINE = 5                      // mm of a line of body text
const CELL_PAD = 1.6
const GREY = 110
const ACCENT: [number, number, number] = [31, 78, 121]

export interface PdfOptions {
  /** Compressed streams (the default) make a smaller file; tests turn it off to read the text back. */
  compress?: boolean
}

class Page {
  y = MARGIN
  constructor(readonly doc: jsPDF) {}

  /** Starts a new page when ``height`` mm do not fit in what is left. */
  ensure(height: number): boolean {
    if (this.y + height <= BOTTOM) return false
    this.doc.addPage()
    this.y = MARGIN
    return true
  }

  lines(text: string, width = WIDTH): string[] {
    return this.doc.splitTextToSize(safeText(text), width) as string[]
  }
}

function title(page: Page, block: Extract<Block, { kind: 'title' }>): void {
  const { doc } = page
  doc.setFont('helvetica', 'bold').setFontSize(17).setTextColor(...ACCENT)
  const lines = page.lines(block.text)
  doc.text(lines, MARGIN, page.y + 6)
  page.y += 6 + (lines.length - 1) * 7
  doc.setFont('helvetica', 'normal').setFontSize(11).setTextColor(GREY)
  doc.text(safeText(block.sub), MARGIN, page.y + 6)
  page.y += 12
  doc.setTextColor(0)
}

function heading(page: Page, block: Extract<Block, { kind: 'heading' }>): void {
  page.ensure(16)        // a heading is never left alone at the bottom of a page
  const { doc } = page
  page.y += 4
  doc.setFont('helvetica', 'bold').setFontSize(13).setTextColor(...ACCENT)
  doc.text(safeText(block.text), MARGIN, page.y + 5)
  doc.setDrawColor(...ACCENT).setLineWidth(0.3).line(MARGIN, page.y + 7, MARGIN + WIDTH, page.y + 7)
  page.y += 11
  doc.setTextColor(0)
}

function paragraph(page: Page, text: string, bold = false, indent = 0, bullet = false): void {
  const { doc } = page
  doc.setFont('helvetica', bold ? 'bold' : 'normal').setFontSize(10)
  const lines = page.lines(text, WIDTH - indent)
  lines.forEach((line, i) => {
    page.ensure(LINE)
    if (bullet && i === 0) doc.text('-', MARGIN + indent - 4, page.y + 4)
    doc.text(line, MARGIN + indent, page.y + 4)
    page.y += LINE
  })
  page.y += 1.5
}

function table(page: Page, block: Extract<Block, { kind: 'table' }>): void {
  const { doc } = page
  const fractions = block.widths ?? block.head.map(() => 1 / block.head.length)
  const widths = fractions.map(f => f * WIDTH)
  const drawHead = () => {
    page.ensure(8)
    doc.setFillColor(...ACCENT).rect(MARGIN, page.y, WIDTH, 6.5, 'F')
    doc.setFont('helvetica', 'bold').setFontSize(9).setTextColor(255)
    let x = MARGIN
    block.head.forEach((h, i) => { doc.text(safeText(h), x + CELL_PAD, page.y + 4.5); x += widths[i] })
    doc.setTextColor(0)
    page.y += 6.5
  }
  drawHead()
  doc.setFont('helvetica', 'normal').setFontSize(9)
  block.rows.forEach((row, r) => {
    const cells = row.map((cell, i) => page.lines(cell, widths[i] - 2 * CELL_PAD))
    const height = Math.max(...cells.map(c => c.length)) * 4 + 2 * CELL_PAD - 1
    if (page.ensure(height)) { drawHead(); doc.setFont('helvetica', 'normal').setFontSize(9) }
    if (r % 2 === 1) doc.setFillColor(240, 243, 247).rect(MARGIN, page.y, WIDTH, height, 'F')
    let x = MARGIN
    cells.forEach((lines, i) => { doc.text(lines, x + CELL_PAD, page.y + CELL_PAD + 2.2); x += widths[i] })
    page.y += height
  })
  page.y += 3
}

function chart(page: Page, block: Extract<Block, { kind: 'chart' }>): void {
  const { doc } = page
  const height = 48
  page.ensure(height + 8)
  const top = page.y + 2
  const end = Math.max(2400, ...block.points.map(p => p[0]))
  const span = Math.max(5, ...block.points.map(p => Math.abs(p[1])))
  const x = (t: number) => MARGIN + (t / end) * WIDTH
  const y = (net: number) => top + height / 2 - (net / span) * (height / 2)
  doc.setDrawColor(200).setLineWidth(0.2).rect(MARGIN, top, WIDTH, height)
  for (let q = 600; q < end; q += 600) doc.line(x(q), top, x(q), top + height)
  doc.setDrawColor(120).line(MARGIN, y(0), MARGIN + WIDTH, y(0))
  doc.setDrawColor(...ACCENT).setLineWidth(0.6)
  block.points.slice(1).forEach(([t, net], i) => doc.line(x(block.points[i][0]), y(block.points[i][1]), x(t), y(net)))
  doc.setFont('helvetica', 'normal').setFontSize(7).setTextColor(GREY)
  doc.text(`+${span}`, MARGIN + 1, top + 3)
  doc.text(`-${span}`, MARGIN + 1, top + height - 1)
  ;[1, 2, 3, 4].forEach(q => doc.text(`Q${q}`, x((q - 1) * 600) + 1.5, top + height + 3.5))
  doc.setTextColor(0)
  page.y = top + height + 7
}

function footers(doc: jsPDF): void {
  const total = doc.getNumberOfPages()
  for (let i = 1; i <= total; i++) {
    doc.setPage(i)
    doc.setFont('helvetica', 'normal').setFontSize(8).setTextColor(GREY)
    doc.text(`BasketLab Live · Página ${i} de ${total}`, PAGE.w / 2, PAGE.h - 8, { align: 'center' })
  }
}

/** The blocks as a PDF file (bytes). */
export async function renderPdf(blocks: Block[], { compress = true }: PdfOptions = {}): Promise<Uint8Array> {
  const { jsPDF: PDF } = await import('jspdf')
  const doc = new PDF({ unit: 'mm', format: 'a4', compress })
  const page = new Page(doc)
  for (const block of blocks) {
    if (block.kind === 'title') title(page, block)
    else if (block.kind === 'heading') heading(page, block)
    else if (block.kind === 'text') paragraph(page, block.text, block.bold)
    else if (block.kind === 'bullets') block.items.forEach(item => paragraph(page, item, false, 5, true))
    else if (block.kind === 'table') table(page, block)
    else chart(page, block)
  }
  footers(doc)
  return new Uint8Array(doc.output('arraybuffer'))
}
