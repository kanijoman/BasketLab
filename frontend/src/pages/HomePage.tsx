/**
 * HomePage — landing page and collection selector.
 *
 * Lets the user choose FEB or FBCYL, fill in the competition details,
 * and navigate to the collection workspace.
 * Recent collections are stored in localStorage for quick access.
 */
import { useState, FormEvent, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Clock, ChevronRight, AlertCircle } from 'lucide-react'
import { resolveCollectionName } from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'

const RECENTS_KEY = 'mfa-recent-collections'
const MAX_RECENTS = 5

interface RecentCollection {
  name: string
  label: string
  isFbcyl: boolean
  accessedAt: string
}

function loadRecents(): RecentCollection[] {
  try {
    return JSON.parse(localStorage.getItem(RECENTS_KEY) ?? '[]')
  } catch {
    return []
  }
}

function saveRecent(name: string, isFbcyl: boolean) {
  const recents = loadRecents().filter(r => r.name !== name)
  const parts = name.split('_')
  const label = parts.length > 1 ? `${parts[0]} · ${parts.slice(1).join(' ')}` : name
  recents.unshift({ name, label, isFbcyl, accessedAt: new Date().toISOString() })
  try {
    localStorage.setItem(RECENTS_KEY, JSON.stringify(recents.slice(0, MAX_RECENTS)))
  } catch { /* ignore */ }
}

// ── League selector card ──────────────────────────────────────────────────────
interface LeagueCardProps {
  title: string
  subtitle: string
  badge: string
  selected: boolean
  onClick: () => void
}

function LeagueCard({ title, subtitle, badge, selected, onClick }: LeagueCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left p-4 rounded-card border transition-all ${
        selected
          ? 'border-brand-500 bg-brand-600/10 shadow-glow'
          : 'border-surface-border hover:border-ink-muted hover:bg-surface-hover'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className={`font-semibold text-sm ${selected ? 'text-brand-400' : 'text-ink-primary'}`}>
            {title}
          </p>
          <p className="text-xs text-ink-secondary mt-0.5">{subtitle}</p>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-pill font-medium shrink-0 ${
          selected ? 'bg-brand-600/30 text-brand-400' : 'bg-surface-border text-ink-muted'
        }`}>
          {badge}
        </span>
      </div>
    </button>
  )
}

export default function HomePage() {
  const navigate = useNavigate()
  const [league, setLeague] = useState<'FEB' | 'FBCYL'>('FEB')
  const [season, setSeason] = useState('LF2_2025')
  const [group, setGroup] = useState('A')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [recents, setRecents] = useState<RecentCollection[]>([])

  useEffect(() => {
    setRecents(loadRecents())
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const { collection_name } = await resolveCollectionName(league, season, group)
      saveRecent(collection_name, league === 'FBCYL')
      navigate(`/${encodeURIComponent(collection_name)}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'No se pudo resolver la colección')
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageTransition>
      <div className="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center px-4 py-12">
        <div className="w-full max-w-lg space-y-8">

          {/* Header */}
          <div className="text-center space-y-2">
            <div className="flex items-center justify-center gap-3 mb-4">
              <img
                src="/logo.png"
                alt="MetricsForAll"
                className="h-12 w-12 rounded-xl shadow-card"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
              <h1 className="text-3xl font-bold text-ink-primary tracking-tight">
                MetricsForAll
              </h1>
            </div>
            <p className="text-ink-secondary text-sm">
              Análisis estadístico de baloncesto · Ligas españolas FEB / FBCYL
            </p>
          </div>

          {/* Form card */}
          <div className="card p-6 space-y-5">
            <h2 className="text-sm font-semibold text-ink-primary">Seleccionar competición</h2>

            {/* League selector */}
            <div className="grid grid-cols-2 gap-3">
              <LeagueCard
                title="FEB"
                subtitle="Liga Nacional"
                badge="Nacional"
                selected={league === 'FEB'}
                onClick={() => setLeague('FEB')}
              />
              <LeagueCard
                title="FBCYL"
                subtitle="Castilla y León"
                badge="Regional"
                selected={league === 'FBCYL'}
                onClick={() => setLeague('FBCYL')}
              />
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Season */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-ink-secondary">Temporada</label>
                <input
                  type="text"
                  value={season}
                  onChange={e => setSeason(e.target.value)}
                  placeholder="Ej: LF2_2025"
                  className="input"
                  required
                />
              </div>

              {/* Group */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-ink-secondary">Grupo</label>
                <input
                  type="text"
                  value={group}
                  onChange={e => setGroup(e.target.value)}
                  placeholder="Ej: A"
                  className="input"
                  required
                />
              </div>

              {error && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-down/10 border border-down/20 text-down text-sm">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="btn-primary w-full justify-center py-2.5 disabled:opacity-50"
              >
                {loading ? 'Cargando…' : 'Abrir colección'}
              </button>
            </form>
          </div>

          {/* Recent collections */}
          {recents.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs text-ink-muted">
                <Clock className="w-3.5 h-3.5" />
                Accesos recientes
              </div>
              <div className="space-y-1">
                {recents.map(r => (
                  <button
                    key={r.name}
                    onClick={() => navigate(`/${encodeURIComponent(r.name)}`)}
                    className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg
                               bg-surface-raised border border-surface-border
                               hover:border-brand-600/40 hover:bg-surface-hover
                               transition-colors text-left group"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${
                        r.isFbcyl ? 'bg-accent-600/20 text-accent-400' : 'bg-brand-600/20 text-brand-400'
                      }`}>
                        {r.isFbcyl ? 'FBCYL' : 'FEB'}
                      </span>
                      <span className="text-sm text-ink-primary truncate">{r.label}</span>
                    </div>
                    <ChevronRight className="w-3.5 h-3.5 text-ink-muted group-hover:text-ink-primary transition-colors shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </PageTransition>
  )
}
