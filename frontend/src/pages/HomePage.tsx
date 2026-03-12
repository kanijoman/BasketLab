import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { resolveCollectionName } from '@/api/client'

/**
 * Landing page — lets the user select a competition / season / group
 * and navigate to the statistics views.
 */
export default function HomePage() {
  const navigate = useNavigate()
  const [competition, setCompetition] = useState('FEB')
  const [season, setSeason] = useState('LF2_2025')
  const [group, setGroup] = useState('A')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const { collection_name } = await resolveCollectionName(competition, season, group)
      navigate(`/teams/${encodeURIComponent(collection_name)}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto mt-16">
      <h1 className="text-3xl font-bold text-court-950 mb-2">
        Estadísticas de Baloncesto
      </h1>
      <p className="text-gray-500 mb-8 text-sm">
        Selecciona la competición, temporada y grupo para explorar las
        estadísticas de equipo y jugadores.
      </p>

      <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow p-6 space-y-4">
        {/* Competition */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Competición
          </label>
          <select
            value={competition}
            onChange={e => setCompetition(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="FEB">FEB — Liga Nacional</option>
            <option value="FBCYL">FBCYL — Liga Castilla y León</option>
          </select>
        </div>

        {/* Season */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Temporada
          </label>
          <input
            type="text"
            value={season}
            onChange={e => setSeason(e.target.value)}
            placeholder="Ej: LF2_2025"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Group */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Grupo
          </label>
          <input
            type="text"
            value={group}
            onChange={e => setGroup(e.target.value)}
            placeholder="Ej: A"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {error && (
          <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded p-2">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-60 text-white font-medium rounded-lg py-2 text-sm transition-colors"
        >
          {loading ? 'Cargando…' : 'Ver estadísticas'}
        </button>
      </form>
    </div>
  )
}
