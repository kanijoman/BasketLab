/** The post-match PDF of a kept match (issue #409) and of a demo or the sample game (issue #477), and the state of the buttons that ask for it. */
import { useCallback, useState } from 'react'
import type { EngineApi } from '../engine/client'
import type { DemoData, DemoMatch, RealDemoData } from '../engine/demo'
import { summarizePackage } from '../package/summary'
import type { PostMatchReport } from '../engine/types'
import { reportBlocks } from '../postmatch/blocks'
import { fileNameFor, sharePdf } from '../postmatch/share'
import type { FinishedStore } from '../feed/finishedStore'
import { SAMPLE } from './DemoControls'

export interface PdfDeps {
  render(report: PostMatchReport): Promise<Uint8Array>
  share(bytes: Uint8Array, fileName: string, title: string): Promise<void>
}
export const defaultPdf: PdfDeps = {
  render: async report => (await import('../postmatch/pdf')).renderPdf(reportBlocks(report)),
  share: (bytes, fileName, title) => sharePdf(bytes, fileName, title),
}

interface Deps {
  engine: EngineApi
  finishedStore: FinishedStore
  pdf: PdfDeps
  record: (line: string) => void
  matches: DemoMatch[]
  demo: DemoData | null
  loadMatch: (match: DemoMatch) => Promise<RealDemoData>
}

export function useMatchReports({ engine, finishedStore, pdf, record, matches, demo, loadMatch }: Deps) {
  const [reporting, setReporting] = useState<string | null>(null)
  const [reportError, setReportError] = useState<string | null>(null)
  const [demoReportError, setDemoReportError] = useState<string | null>(null)

  /** The post-match analysis of a kept match as a PDF the staff can share (issue #409). */
  const reportFinished = useCallback(async (code: string) => {
    setReporting(code)
    setReportError(null)
    try {
      const saved = await finishedStore.load(code)
      if (!saved) throw new Error('el partido ya no está guardado')
      const report = await engine.report(saved.game, saved.alerts ?? [], saved.ownId, summarizePackage(saved.plaintext).ruleConfig)
      const title = `Informe del partido ${report.match.own.name.trim()} – ${report.match.rival.name.trim()}`
      await pdf.share(await pdf.render(report), fileNameFor(report.match.own.name, report.match.rival.name, code), title)
      record(`Informe PDF del partido ${code}`)
    } catch (e) {
      setReportError(`No se pudo generar el informe: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setReporting(null)
    }
  }, [engine, finishedStore, pdf, record])

  /** The PDF report of a demo or of the sample game (issue #477): from the last document of its recording, with the gender of its package. */
  const reportDemo = useCallback(async (value: string) => {
    setReporting(value)
    setDemoReportError(null)
    try {
      const match = matches.find(m => m.code === value)
      const source = value === SAMPLE && demo ? { game: demo.game, package: demo.package } : match ? await loadMatch(match).then(r => ({ game: r.recording, package: r.package })) : null
      if (!source) throw new Error('no se encuentra el partido')
      const summary = summarizePackage(source.package)
      const report = await engine.report(source.game, [], summary.teamId, summary.ruleConfig)
      await pdf.share(await pdf.render(report), fileNameFor(report.match.own.name, report.match.rival.name, value),
        `Informe del partido ${report.match.own.name.trim()} – ${report.match.rival.name.trim()}`)
      record(`Informe PDF de la demostración ${value}`)
    } catch (e) {
      setDemoReportError(`No se pudo generar el informe: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setReporting(null)
    }
  }, [engine, pdf, record, matches, demo, loadMatch])

  return { reporting, reportError, demoReportError, reportFinished, reportDemo }
}
