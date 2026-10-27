/**
 * ExportButton — dropdown to export table/chart data in multiple formats.
 *
 * Supported formats: CSV (client-side), PNG (client-side SVG→canvas), PDF (jsPDF).
 * Pass `tableRef` for table exports and/or `svgRef` for chart exports.
 */
import { useState, useRef, useEffect, RefObject } from 'react'
import { Download, ChevronDown, FileText, Image, Table } from 'lucide-react'
import { cn } from '@/lib/utils'
import { prepareCloneForExport } from '@/lib/exportDom'
import { cssColour } from '@/lib/chartTheme'   // the colours of the theme in use (issues #188, #617)
import { THEME_COLOR } from '@design/theme'
import { collectBreakPoints, computePdfSlices } from '@/lib/pdfLayout'

export interface ExportOptions {
  /** Filename prefix (without extension) */
  filename?: string
  /** Table data for CSV export */
  csvData?: Record<string, unknown>[]
  csvHeaders?: { key: string; label: string }[]
  /** Ref to a DOM element to capture as PNG */
  captureRef?: RefObject<HTMLElement | SVGElement>
  /** Title shown in PDF header */
  pdfTitle?: string
}

interface Props extends ExportOptions {
  className?: string
}

// ── CSV export (client-side) ─────────────────────────────────────────────────
function downloadCsv(
  data: Record<string, unknown>[],
  headers: { key: string; label: string }[],
  filename: string,
) {
  const rows = [
    headers.map(h => `"${h.label}"`).join(','),
    ...data.map(row =>
      headers.map(h => {
        const v = row[h.key]
        if (v == null) return ''
        if (typeof v === 'string' && v.includes(',')) return `"${v}"`
        return String(v)
      }).join(',')
    ),
  ]
  const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `${filename}.csv`; a.click()
  URL.revokeObjectURL(url)
}

// ── PNG export (client-side, SVG or DOM via html2canvas) ────────────────────
/** A chart from its SVG on a canvas at 2x, over the background of the theme in use (issue #617: it was transparent). */
function svgToCanvas(el: SVGElement): Promise<HTMLCanvasElement> {
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(el)], { type: 'image/svg+xml' }))
  return new Promise(resolve => {
    const img = new window.Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = el.clientWidth * 2; canvas.height = el.clientHeight * 2
      const ctx = canvas.getContext('2d')!
      ctx.scale(2, 2)
      ctx.fillStyle = pageColour()
      ctx.fillRect(0, 0, el.clientWidth, el.clientHeight)
      ctx.drawImage(img, 0, 0)
      URL.revokeObjectURL(url)
      resolve(canvas)
    }
    img.src = url
  })
}

/** The background of the page of the theme in use (the light one if the tokens are not there). */
const pageColour = () => cssColour('--bg') || THEME_COLOR.light

async function downloadPng(ref: RefObject<HTMLElement | SVGElement>, filename: string) {
  const el = ref.current
  if (!el) return

  if (el instanceof SVGElement) {
    // Direct SVG → canvas → PNG
    const canvas = await svgToCanvas(el)
    canvas.toBlob(b => {
      if (!b) return
      const link = document.createElement('a')
      link.href = URL.createObjectURL(b); link.download = `${filename}.png`; link.click()
    })
  } else {
    // DOM element — use html2canvas
    const { default: html2canvas } = await import('html2canvas')
    const canvas = await html2canvas(el as HTMLElement, {
      backgroundColor: pageColour(), scale: 2, onclone: prepareCloneForExport,
    })
    canvas.toBlob(b => {
      if (!b) return
      const link = document.createElement('a')
      link.href = URL.createObjectURL(b); link.download = `${filename}.png`; link.click()
    })
  }
}

// ── PDF export ───────────────────────────────────────────────────────────────
const PDF_CAPTURE_SCALE = 2
const PDF_LAYOUT = { pageW: 297, pageH: 210, margin: 14, firstTop: 28 }

/** Paint a page of the PDF with the background of the theme in use (issue #617: it was dark in both themes). */
function paintPage(pdf: import('jspdf').jsPDF) {
  pdf.setFillColor(pageColour())
  pdf.rect(0, 0, PDF_LAYOUT.pageW, PDF_LAYOUT.pageH, 'F')
}

/** Add a (possibly very tall) capture across as many pages as needed. */
async function addPaginatedImage(
  pdf: import('jspdf').jsPDF,
  dataUrl: string,
  breakPoints: number[] = [],
) {
  const img = new window.Image()
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve()
    img.onerror = () => reject(new Error('No se pudo leer la captura'))
    img.src = dataUrl
  })
  const slices = computePdfSlices(img.naturalWidth, img.naturalHeight, PDF_LAYOUT, breakPoints)
  const { pageW, margin } = PDF_LAYOUT
  slices.forEach((sl, i) => {
    if (i > 0) {
      pdf.addPage()
      paintPage(pdf)
    }
    const c = document.createElement('canvas')
    c.width = img.naturalWidth
    c.height = Math.max(1, Math.round(sl.srcH))
    c.getContext('2d')!.drawImage(img, 0, sl.srcY, img.naturalWidth, sl.srcH, 0, 0, c.width, c.height)
    pdf.addImage(c.toDataURL('image/png'), 'PNG', margin, sl.destY, pageW - 2 * margin, sl.destH)
  })
}

async function downloadPdf(
  ref: RefObject<HTMLElement | SVGElement> | undefined,
  title: string,
  filename: string,
) {
  // Dynamic import avoids TypeScript constructor type resolution issues with jsPDF v4
  const { jsPDF: JsPDF } = await import('jspdf')
  const pdf = new JsPDF('l', 'mm', 'a4')
  paintPage(pdf)
  const ink = cssColour('--text'), muted = cssColour('--text-muted')
  if (ink) pdf.setTextColor(ink)
  pdf.setFontSize(14)
  pdf.text(title, 14, 16)
  pdf.setFontSize(9)
  if (muted) pdf.setTextColor(muted)
  pdf.text(`BasketLab · ${new Date().toLocaleDateString('es-ES')}`, 14, 22)

  if (ref?.current) {
    const el = ref.current
    let dataUrl: string | null = null
    let breakPoints: number[] = []

    if (el instanceof SVGElement) {
      dataUrl = (await svgToCanvas(el)).toDataURL('image/png')
    } else {
      const { default: html2canvas } = await import('html2canvas')
      const canvas = await html2canvas(el as HTMLElement, {
        backgroundColor: pageColour(), scale: PDF_CAPTURE_SCALE, onclone: prepareCloneForExport,
      })
      dataUrl = canvas.toDataURL('image/png')
      // pages end between table rows / cards instead of through them
      breakPoints = collectBreakPoints(el as HTMLElement, PDF_CAPTURE_SCALE)
    }

    if (dataUrl) await addPaginatedImage(pdf, dataUrl, breakPoints)
  }

  pdf.save(`${filename}.pdf`)
}

// ── Component ────────────────────────────────────────────────────────────────
export default function ExportButton({
  filename = 'basketlab-export',
  csvData,
  csvHeaders,
  captureRef,
  pdfTitle,
  className,
}: Props) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const hasCsv = Boolean(csvData?.length && csvHeaders?.length)
  const hasPng = Boolean(captureRef)
  const hasPdf = Boolean(captureRef || pdfTitle)

  return (
    <div ref={menuRef} className={cn('relative inline-block', className)}>
      <button
        className="btn-secondary"
        onClick={() => setOpen(o => !o)}
      >
        <Download className="w-3.5 h-3.5" />
        Exportar
        <ChevronDown className={cn('w-3 h-3 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-44 card shadow-panel py-1 z-30">
          {hasCsv && (
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-muted
                         hover:bg-surface-raised hover:text-ink transition-colors"
              onClick={() => {
                downloadCsv(csvData!, csvHeaders!, filename)
                setOpen(false)
              }}
            >
              <Table className="w-3.5 h-3.5" /> CSV
            </button>
          )}
          {hasPng && (
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-muted
                         hover:bg-surface-raised hover:text-ink transition-colors"
              onClick={() => {
                downloadPng(captureRef!, filename)
                setOpen(false)
              }}
            >
              <Image className="w-3.5 h-3.5" /> PNG
            </button>
          )}
          {hasPdf && (
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-muted
                         hover:bg-surface-raised hover:text-ink transition-colors"
              onClick={() => {
                downloadPdf(captureRef, pdfTitle ?? filename, filename)
                setOpen(false)
              }}
            >
              <FileText className="w-3.5 h-3.5" /> PDF
            </button>
          )}
        </div>
      )}
    </div>
  )
}
