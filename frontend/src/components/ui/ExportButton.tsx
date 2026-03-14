/**
 * ExportButton — dropdown to export table/chart data in multiple formats.
 *
 * Supported formats: CSV (client-side), PNG (client-side SVG→canvas), PDF (jsPDF).
 * Pass `tableRef` for table exports and/or `svgRef` for chart exports.
 */
import { useState, useRef, useEffect, RefObject } from 'react'
import { Download, ChevronDown, FileText, Image, Table } from 'lucide-react'
import { cn } from '@/lib/utils'

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
async function downloadPng(ref: RefObject<HTMLElement | SVGElement>, filename: string) {
  const el = ref.current
  if (!el) return

  if (el instanceof SVGElement) {
    // Direct SVG → canvas → PNG
    const serializer = new XMLSerializer()
    const svgStr = serializer.serializeToString(el)
    const blob = new Blob([svgStr], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const img = new window.Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = el.clientWidth * 2; canvas.height = el.clientHeight * 2
      const ctx = canvas.getContext('2d')!
      ctx.scale(2, 2); ctx.drawImage(img, 0, 0)
      canvas.toBlob(b => {
        if (!b) return
        const link = document.createElement('a')
        link.href = URL.createObjectURL(b); link.download = `${filename}.png`; link.click()
      })
      URL.revokeObjectURL(url)
    }
    img.src = url
  } else {
    // DOM element — use html2canvas
    const { default: html2canvas } = await import('html2canvas')
    const canvas = await html2canvas(el as HTMLElement, { backgroundColor: '#0D1117', scale: 2 })
    canvas.toBlob(b => {
      if (!b) return
      const link = document.createElement('a')
      link.href = URL.createObjectURL(b); link.download = `${filename}.png`; link.click()
    })
  }
}

// ── PDF export ───────────────────────────────────────────────────────────────
async function downloadPdf(
  ref: RefObject<HTMLElement | SVGElement> | undefined,
  title: string,
  filename: string,
) {
  // Dynamic import avoids TypeScript constructor type resolution issues with jsPDF v4
  const { jsPDF: JsPDF } = await import('jspdf')
  const pdf = new JsPDF('l', 'mm', 'a4')
  pdf.setFillColor(13, 17, 23)
  pdf.rect(0, 0, 297, 210, 'F')
  pdf.setTextColor(230, 237, 243)
  pdf.setFontSize(14)
  pdf.text(title, 14, 16)
  pdf.setFontSize(9)
  pdf.setTextColor(139, 148, 158)
  pdf.text(`MetricsForAll · ${new Date().toLocaleDateString('es-ES')}`, 14, 22)

  if (ref?.current) {
    const el = ref.current
    let dataUrl: string | null = null

    if (el instanceof SVGElement) {
      const serializer = new XMLSerializer()
      const svgStr = serializer.serializeToString(el)
      const blob = new Blob([svgStr], { type: 'image/svg+xml' })
      const url = URL.createObjectURL(blob)
      await new Promise<void>(resolve => {
        const img = new window.Image()
        img.onload = () => {
          const canvas = document.createElement('canvas')
          canvas.width = el.clientWidth * 2; canvas.height = el.clientHeight * 2
          const ctx = canvas.getContext('2d')!
          ctx.scale(2, 2); ctx.drawImage(img, 0, 0)
          dataUrl = canvas.toDataURL('image/png')
          URL.revokeObjectURL(url)
          resolve()
        }
        img.src = url
      })
    } else {
      const { default: html2canvas } = await import('html2canvas')
      const canvas = await html2canvas(el as HTMLElement, { backgroundColor: '#0D1117', scale: 2 })
      dataUrl = canvas.toDataURL('image/png')
    }

    if (dataUrl) {
      pdf.addImage(dataUrl, 'PNG', 14, 28, 269, 0)
    }
  }

  pdf.save(`${filename}.pdf`)
}

// ── Component ────────────────────────────────────────────────────────────────
export default function ExportButton({
  filename = 'metricsforall-export',
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
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-secondary
                         hover:bg-surface-hover hover:text-ink-primary transition-colors"
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
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-secondary
                         hover:bg-surface-hover hover:text-ink-primary transition-colors"
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
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-secondary
                         hover:bg-surface-hover hover:text-ink-primary transition-colors"
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
