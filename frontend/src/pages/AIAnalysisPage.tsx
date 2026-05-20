/**
 * AIAnalysisPage — Fase 4
 * Análisis IA con streaming SSE, react-markdown y export MD.
 */
import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bot, ChevronDown, Zap, Copy, Download, Square, FileText, FileDown, Loader2, CheckCircle2 } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import {
  getAIAnalysisStreamUrl,
  downloadIndividualScoutingDocx,
  type TeamEntry,
  exportAIAnalysisPDF,
  type AIAnalysisRequest,
} from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'

// -- Constants ----------------------------------------------------------------

const ANALYSIS_TYPES = [
  { key: 'own',        label: 'Propio equipo',       desc: 'Análisis de rendimiento propio'              },
  { key: 'scouting',  label: 'Scouting rival',      desc: 'Informe de análisis pre-partido'             },
  { key: 'individual', label: 'Scouting Individual', desc: 'Informe de plantilla completa por jugador'  },
] as const

const PROVIDERS = [
  { key: 'groq',   label: 'Groq',   icon: '⚡', desc: 'Llama 3.3 70B · Rápido' },
  { key: 'gemini', label: 'Gemini', icon: '✨', desc: 'Gemini 2.0 Flash'         },
  { key: 'openai', label: 'OpenAI', icon: '🔮', desc: 'GPT-4o Mini'              },
] as const

// -- Component ----------------------------------------------------------------

export default function AIAnalysisPage() {
  const { collection } = useCollection()

  const [team, setTeam] = useState('')
  const [analysisType, setAnalysisType] = useState<'own' | 'scouting' | 'individual'>('own')
  const [provider, setProvider] = useState<'groq' | 'gemini' | 'openai'>('groq')
  const [includeRecs, setIncludeRecs] = useState(true)

  const [content, setContent] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [docxLoading, setDocxLoading] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [docxStep, setDocxStep] = useState(0)

  const DOCX_STEPS = [
    'Recopilando datos de jugadores…',
    'Generando perfiles de tiro…',
    'Calculando estadísticas avanzadas…',
    'Creando gráficos de radar…',
    'Añadiendo notas IA…',
    'Compilando documento DOCX…',
  ]

  useEffect(() => {
    if (!docxLoading) { setDocxStep(0); return }
    const id = setInterval(() =>
      setDocxStep(s => s < DOCX_STEPS.length - 1 ? s + 1 : s)
    , 5000)
    return () => clearInterval(id)
  }, [docxLoading])
  // Throttled iframe content — update every 800ms during streaming to avoid thrashing
  const [renderDoc, setRenderDoc] = useState('')
  useEffect(() => {
    if (!streaming) { setRenderDoc(content); return }
    const t = setTimeout(() => setRenderDoc(content), 800)
    return () => clearTimeout(t)
  }, [content, streaming])

  const esRef = useRef<EventSource | null>(null)
  const contentRef = useRef('')
  const scrollRef = useRef<HTMLDivElement>(null)

  // Team list
  const { data: teamList = [] } = useQuery<TeamEntry[]>({
    queryKey: ['team-list', collection?.name],
    queryFn: () =>
      fetch(`/api/v1/teams/${encodeURIComponent(collection!.name)}/teams`).then(r => r.json()),
    enabled: Boolean(collection),
    staleTime: 10 * 60_000,
  })

  // Derive display name from selected team ID
  const teamDisplayName = teamList.find(t => t.id === team)?.name ?? team

  // Auto-scroll while streaming
  useEffect(() => {
    if (streaming) scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [content, streaming])

  function stopStream() {
    esRef.current?.close()
    esRef.current = null
    setStreaming(false)
  }

  function startAnalysis() {
    if (!collection || !team) return
    setContent('')
    contentRef.current = ''
    setRenderDoc('')
    setError(null)
    setDone(false)

    // Individual scouting has no streaming — the product is the DOCX
    if (analysisType === 'individual') {
      setDone(true)
      return
    }

    setStreaming(true)

    const req: AIAnalysisRequest = {
      collection: collection.name,
      team_id: team,
      analysis_type: analysisType,
      provider,
      include_recommendations: includeRecs,
    }

    const url = getAIAnalysisStreamUrl(req)
    const es = new EventSource(url)
    esRef.current = es

    es.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data) as Record<string, unknown>
        if (typeof parsed.chunk === 'string') {
          contentRef.current += parsed.chunk
          setContent(contentRef.current)
        } else if (parsed.done) {
          setDone(true)
          setStreaming(false)
          es.close()
        } else if (typeof parsed.error === 'string') {
          setError(parsed.error)
          setStreaming(false)
          es.close()
        }
      } catch { /* ignore malformed chunks */ }
    }

    es.onerror = () => {
      setError('Error de conexión con el servidor. Inténtalo de nuevo.')
      setStreaming(false)
      es.close()
    }
  }

  function copyToClipboard() { navigator.clipboard.writeText(content) }

  function downloadMarkdown() {
    const blob = new Blob([content], { type: 'text/markdown' })
    const url  = URL.createObjectURL(blob)
    const a    = Object.assign(document.createElement('a'), {
      href:     url,
      download: `analisis_${teamDisplayName.replace(/\s+/g, '_')}_${Date.now()}.md`,
    })
    a.click()
    URL.revokeObjectURL(url)
  }

  async function handleDownloadDocx() {
    if (!collection || !team) return
    setDocxLoading(true)
    try {
      const blob = await downloadIndividualScoutingDocx(collection.name, team)
      const url = URL.createObjectURL(blob)
      const a = Object.assign(document.createElement('a'), {
        href: url,
        download: `Scouting_${teamDisplayName.replace(/\s+/g, '_')}.docx`,
      })
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error descargando DOCX')
    } finally {
      setDocxLoading(false)
    }
  }

  async function handleExportPDF() {
    if (!content) return
    setPdfLoading(true)
    try {
      const blob = await exportAIAnalysisPDF(content, team, analysisType)
      const url = URL.createObjectURL(blob)
      const label = analysisType === 'scouting' ? 'Scouting' : 'Analisis'
      const a = Object.assign(document.createElement('a'), {
        href: url,
        download: `${label}_${team.replace(/\s+/g, '_')}.pdf`,
      })
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error generando PDF')
    } finally {
      setPdfLoading(false)
    }
  }

  const canStart = Boolean(collection) && Boolean(team) && !streaming

  return (
    <PageTransition>
      <div className="space-y-4">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Análisis IA</h1>
          <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
        </div>

        {/* Config row */}
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto_auto] gap-3">
          {/* Team */}
          <div className="card p-3 flex flex-col gap-1.5">
            <label className="text-xs text-ink-secondary font-medium uppercase tracking-wide">Equipo</label>
            <div className="relative">
              <select
                value={team}
                onChange={e => setTeam(e.target.value)}
                className="w-full appearance-none bg-surface-base border border-surface-border rounded-lg px-3 py-2 pr-8 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400"
              >
                <option value="">— Selecciona equipo —</option>
                {teamList.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-secondary" />
            </div>
          </div>

          {/* Analysis type */}
          <div className="card p-3 flex flex-col gap-1.5 min-w-[180px]">
            <label className="text-xs text-ink-secondary font-medium uppercase tracking-wide">Tipo</label>
            {ANALYSIS_TYPES.map(at => (
              <label key={at.key} className="flex items-center gap-2 cursor-pointer text-sm">
                <input type="radio" name="at" value={at.key} checked={analysisType === at.key}
                  onChange={() => setAnalysisType(at.key)} className="accent-accent-500" />
                <span className="text-ink-primary">{at.label}</span>
              </label>
            ))}
          </div>

          {/* Provider */}
          <div className="card p-3 flex flex-col gap-1.5 min-w-[160px]">
            <label className="text-xs text-ink-secondary font-medium uppercase tracking-wide">Proveedor</label>
            {PROVIDERS.map(p => (
              <label key={p.key} className="flex items-center gap-2 cursor-pointer text-sm">
                <input type="radio" name="prov" value={p.key} checked={provider === p.key}
                  onChange={() => setProvider(p.key)} className="accent-accent-500" />
                <span className="text-ink-primary">{p.icon} {p.label}</span>
              </label>
            ))}
          </div>

          {/* Options + Run */}
          <div className="card p-3 flex flex-col gap-3 justify-between min-w-[140px]">
            <label className={`flex items-center gap-2 text-sm ${analysisType === 'individual' ? 'opacity-35 cursor-not-allowed' : 'cursor-pointer'}`}>
              <input type="checkbox" checked={includeRecs} disabled={analysisType === 'individual'}
                onChange={e => setIncludeRecs(e.target.checked)} className="rounded accent-accent-500 disabled:cursor-not-allowed" />
              <span className="text-ink-secondary text-xs">Recomendaciones</span>
            </label>
            <div className="flex flex-col gap-2">
              {streaming ? (
                <button onClick={stopStream}
                  className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-red-500/20 text-red-400 border border-red-500/30 text-sm font-medium hover:bg-red-500/30 transition-colors">
                  <Square className="w-4 h-4" /> Detener
                </button>
              ) : (
                <button onClick={startAnalysis} disabled={!canStart}
                  className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-accent-500 text-white text-sm font-medium hover:bg-accent-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                  <Zap className="w-4 h-4" /> Analizar
                </button>
              )}
              {done && (
                <>
                  {content && (
                    <>
                      <button onClick={copyToClipboard}
                        className="flex items-center justify-center gap-1 px-2 py-1.5 rounded border border-surface-border text-xs text-ink-secondary hover:bg-surface-hover transition-colors">
                        <Copy className="w-3.5 h-3.5" /> Copiar
                      </button>
                      <button onClick={downloadMarkdown}
                        className="flex items-center justify-center gap-1 px-2 py-1.5 rounded border border-surface-border text-xs text-ink-secondary hover:bg-surface-hover transition-colors">
                        <Download className="w-3.5 h-3.5" /> .md
                      </button>
                    </>
                  )}
                  {analysisType === 'individual' && (
                    <button
                      onClick={handleDownloadDocx}
                      disabled={docxLoading}
                      className="flex items-center justify-center gap-1 px-2 py-1.5 rounded border border-accent-500/50 text-xs text-accent-400 hover:bg-accent-500/10 disabled:opacity-50 transition-colors"
                    >
                      {docxLoading
                        ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        : <FileText className="w-3.5 h-3.5" />}
                      {docxLoading ? 'Generando…' : 'DOCX'}
                    </button>
                  )}
                  {(analysisType === 'own' || analysisType === 'scouting') && content && (
                    <button
                      onClick={handleExportPDF}
                      disabled={pdfLoading}
                      className="flex items-center justify-center gap-1 px-2 py-1.5 rounded border border-accent-500/50 text-xs text-accent-400 hover:bg-accent-500/10 disabled:opacity-50 transition-colors"
                    >
                      <FileDown className="w-3.5 h-3.5" />
                      {pdfLoading ? '…' : 'PDF'}
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Content area */}
        <div className="card p-4 min-h-[300px]">
          {/* Empty state */}
          {!content && !streaming && !error && !done && (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-center">
              <Bot className="w-12 h-12 text-accent-400 opacity-40" />
              <p className="text-ink-secondary text-sm max-w-sm">
                Selecciona un equipo y pulsa <strong>Analizar</strong> para generar
                un informe con IA.
              </p>
            </div>
          )}

          {/* Individual type — DOCX generating progress */}
          {analysisType === 'individual' && done && docxLoading && (
            <div className="flex flex-col items-center justify-center h-56 gap-4">
              <Loader2 className="w-10 h-10 text-accent-400 animate-spin" />
              <p className="text-ink-primary text-sm font-medium">Generando informe DOCX…</p>
              <ul className="space-y-1.5 text-sm">
                {DOCX_STEPS.map((label, i) => (
                  <li key={i} className={`flex items-center gap-2 transition-colors ${
                    i < docxStep  ? 'text-ink-secondary line-through opacity-50'
                    : i === docxStep ? 'text-accent-400 font-medium'
                    : 'text-ink-tertiary opacity-40'
                  }`}>
                    {i < docxStep
                      ? <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
                      : i === docxStep
                        ? <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                        : <span className="w-4 h-4 shrink-0" />}
                    {label}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Individual type — no stream, just a download prompt */}
          {analysisType === 'individual' && done && !docxLoading && (
            <div className="flex flex-col items-center justify-center h-48 gap-3 text-center">
              <FileText className="w-12 h-12 text-accent-400 opacity-60" />
              <p className="text-ink-secondary text-sm max-w-sm">
                El <strong>Scouting Individual</strong> genera un informe DOCX con estadísticas,
                gráficos y notas IA para cada jugador del equipo.
              </p>
              <p className="text-ink-tertiary text-xs">Pulsa el botón <strong>DOCX</strong> para descargar el informe.</p>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          )}

          {/* HTML report rendered in isolated iframe */}
          {(content || streaming) && analysisType !== 'individual' && (
            <div className="space-y-2">
              {streaming && (
                <div className="flex items-center gap-2 text-xs text-accent-400 mb-2">
                  <span className="w-2 h-2 rounded-full bg-accent-400 animate-pulse" />
                  Generando análisis…
                </div>
              )}
              <iframe
                srcDoc={renderDoc || '<body style="background:#f8f8f8;color:#555;font-family:sans-serif;padding:20px">Cargando…</body>'}
                className="w-full rounded-lg border border-surface-border"
                style={{ height: '560px' }}
                sandbox="allow-same-origin"
                title="Análisis IA"
              />
              <div ref={scrollRef} />
            </div>
          )}
        </div>
      </div>
    </PageTransition>
  )
}
