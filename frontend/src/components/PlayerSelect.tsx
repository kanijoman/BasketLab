/** Player picker: name search + team filter + player dropdown (IN/OUT page). */
import { useMemo, useState } from 'react'
import type { PlayerStat } from '@/api/client'

export type TeamOption = { id: string; name: string }

export default function PlayerSelect({
  label, value, onChange, players, teams: teamsProp,
}: { label: string; value: string; onChange: (v: string) => void; players: PlayerStat[]; teams?: TeamOption[] }) {
  const [nameFilter, setNameFilter] = useState('')
  const [teamFilter, setTeamFilter] = useState('')

  // Derive {id, name} pairs from the loaded players when no independent list is available
  const derivedTeams = useMemo((): TeamOption[] => {
    const map = new Map<string, string>()
    for (const p of players) {
      const id = String(p.team_id ?? '')
      const name = (p.team_name ?? '').trim()
      if (id && name) map.set(id, name)
    }
    return Array.from(map.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [players])

  // Prefer independent team list (from getTeamStats) to decouple dropdown
  // availability from full player load
  const teams = teamsProp && teamsProp.length > 0 ? teamsProp : derivedTeams

  const filtered = useMemo(
    () => players.filter(p => {
      // Use team_id for stable matching — team names can change during the season
      const matchesTeam = teamFilter === '' || String(p.team_id ?? '') === teamFilter
      const matchesName = nameFilter === '' || p.player_name.toLowerCase().includes(nameFilter.toLowerCase())
      return matchesTeam && matchesName
    }),
    [players, teamFilter, nameFilter],
  )

  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs text-ink-secondary font-medium uppercase tracking-wide">{label}</label>
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Buscar nombre…"
          value={nameFilter}
          onChange={e => setNameFilter(e.target.value)}
          className="min-w-0 flex-1 bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-primary placeholder-ink-muted focus:outline-none focus:ring-2 focus:ring-accent-400"
        />
        <select
          value={teamFilter}
          onChange={e => setTeamFilter(e.target.value)}
          className="min-w-0 max-w-[50%] bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400"
        >
          <option value="">Todos los equipos</option>
          {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full min-w-0 bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400">
        <option value="">— Selecciona jugador —</option>
        {filtered.map((p, idx) => (
          <option key={`${p.player_id}_${(p.team_name ?? '').trim()}_${idx}`} value={p.player_id}>
            {p.player_name} ({(p.team_name ?? '').trim() || '—'})
          </option>
        ))}
      </select>
    </div>
  )
}
